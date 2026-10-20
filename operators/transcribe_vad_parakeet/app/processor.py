# Script created by opencode:e-research/arc:apex
# Prompt: processor for the transcribe_vad_parakeet operator: like the transcribe_speech_parakeet one but
# transcribing only the voice segments listed in the voice_segments.json next to the input sound, over a
# compacted voice-only temporary wav, and returning the layout mapping the compacted timecodes back to the ones of the clip.

import torch
from pathlib import Path
import sys
import json
import uuid
from flask import Flask, request, jsonify
import signal
import os

import numpy
import soundfile as sf

PARAMS = json.loads(Path('/app/params.json').read_text())

PORT = 5000
# https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3
MODEL = PARAMS['model']
SEGMENTS_FILE_NAME = 'voice_segments.json'
SEGMENTS_FALLBACK_GAP_SECONDS = 0.25
TEMP_SOUND_FOLDER = '/tmp'

'''
Usage:

1. Single transcription from command line:

`python processor.py /path/to/my/sound.wav`

2. Bulk transcription from a http service:

2.1 load the model and service

`python processor.py serve`

2.2 call the service

`curl localhost:5000/process?input_path=/path/to/my/sound.wav`

2.3 stop the service

`curl localhost:5000/stop`

The sound must be accompanied by a voice_segments.json file
in the same folder (the output of detect_speech_vad),
listing the voice segments ({start, end} in seconds) to transcribe.

Only these voice segments are transcribed: they are compacted into a
single temporary wav, separated by short silences, which is transcribed
in a single call. The timecodes of the returned segments are still
relative to that compacted wav; the layout returned along them maps
its timecodes back to the ones of the clip sound (the operator does
the mapping).

In all cases responses are in json:

on success:

{
    "error": "",
    "result": [
        {
            "segment": "This is play acting, but in reality it's designed to shock.",
            "start_offset": 62,
            "end_offset": 116,
            "start": 4.96,
            "end": 9.28
        },
    ],
    "layout": [
        {
            "original_start": 4.96,
            "original_end": 9.28,
            "compact_start": 0.0,
            "compact_end": 4.32
        },
    ]
}

(on success the timecodes in result are yet relative to the compacted wav,
and each layout entry locates one voice segment within the clip sound,
original_start/original_end, and within the compacted wav,
compact_start/compact_end)

on failure:

{
    "error": "ERROR MESSAGE",
    "result": [],
    "layout": []
}

'''

class Transcriber:
    '''Transcribes the voice segments of a clip sound into text segments'''

    def __init__(self):
        import nemo.collections.asr as nemo_asr

        self.device = 'cpu'
        if torch.cuda.is_available() and not PARAMS['cpu_only']:
            self.device = 'cuda'

        self.model = nemo_asr.models.ASRModel.from_pretrained(
            model_name=MODEL,
            map_location=self.device
        )
        # use local attention to avoid OOM errors on long-form audio
        self.model.change_attention_model(self_attention_model="rel_pos_local_attn", att_context_size=[256, 256])

    def transcribe(self, sound_path) -> dict:
        '''Transcribes only the content of the voice segments listed in the
        voice_segments.json sitting next to the sound; returns the transcribed
        segments, with timecodes yet relative to the compacted voice-only
        sound, and the layout used to compact the voice segments'''
        ret = {
            'error': '',
            'result': [],
            'layout': [],
        }

        sound_path = Path(sound_path)
        voice_segments_path = sound_path.parent / SEGMENTS_FILE_NAME

        if not voice_segments_path.is_file():
            ret['error'] = f'voice segments not found: {voice_segments_path}'
        else:
            voice_segments = json.loads(voice_segments_path.read_text())
            voice_segments = self._get_valid_voice_segments(voice_segments)

            if voice_segments:
                # a single temporary sound holding only the voice segments, so
                # the model never listens to the non-speech parts of the clip
                compact = self._compact_voice_segments(sound_path, voice_segments)
                temp_sound_path = compact['temp_sound_path']

                # None when no voice segment falls within the clip sound
                # (e.g. they all lie past its end): nothing to transcribe
                if temp_sound_path:
                    try:
                        output = self.model.transcribe([str(temp_sound_path)], timestamps=True)
                    finally:
                        temp_sound_path.unlink(missing_ok=True)

                    ret['result'] = output[0].timestamp['segment']
                    ret['layout'] = compact['layout']

        return ret

    def _get_valid_voice_segments(self, voice_segments: list) -> list:
        '''Returns the voice segments which end after their start, sorted by their start'''
        ret = [
            segment for segment in voice_segments
            if segment.get('end', 0) > segment.get('start', 0)
        ]
        ret = sorted(ret, key=lambda segment: segment['start'])
        return ret

    def _compact_voice_segments(self, sound_path: Path, voice_segments: list) -> dict:
        '''Writes into a temporary wav the voice segments of the clip sound,
        separated by short silences; returns the path of the temporary sound
        and the layout (the timecodes of each voice segment within the clip
        sound, original_start/original_end, and within the temporary sound,
        compact_start/compact_end)'''
        ret = {}

        sound, sampling_rate = sf.read(str(sound_path))

        gap_seconds = PARAMS.get('segments_gap_seconds', SEGMENTS_FALLBACK_GAP_SECONDS)
        gap_samples = int(gap_seconds * sampling_rate)
        gap = numpy.zeros((gap_samples,) + sound.shape[1:], dtype=sound.dtype)

        pieces = []
        layout = []
        offset_samples = 0

        for segment in voice_segments:
            start_sample = max(0, round(segment['start'] * sampling_rate))
            end_sample = min(len(sound), round(segment['end'] * sampling_rate))

            if start_sample >= end_sample:
                continue

            piece = sound[start_sample:end_sample]

            pieces.append(piece)
            pieces.append(gap)

            layout.append({
                'original_start': start_sample / sampling_rate,
                'original_end': end_sample / sampling_rate,
                'compact_start': offset_samples / sampling_rate,
                'compact_end': (offset_samples + len(piece)) / sampling_rate,
            })

            offset_samples += len(piece) + gap_samples

        temp_sound_path = None

        if pieces:
            temp_sound_path = Path(TEMP_SOUND_FOLDER) / f'{uuid.uuid4().hex}-voice-segments.wav'
            sf.write(str(temp_sound_path), numpy.concatenate(pieces), sampling_rate, subtype='PCM_16')

        ret = {
            'temp_sound_path': temp_sound_path,
            'layout': layout,
        }

        return ret


if __name__ == '__main__':
    response = {
        'error': 'input sound not provided',
        'result': [],
        'layout': [],
    }

    # read the sound file name from the first comamnd line argument
    arguments = sys.argv

    if len(arguments) > 1:
        first_arg = arguments[1]

        transcriber = Transcriber()

        if first_arg == 'serve':
            app = Flask(__name__)

            @app.route('/process', methods=['GET'])
            def transcribe():
                sound_path = request.args.get('input_path', None)

                if sound_path:
                    res = transcriber.transcribe(sound_path)
                    response = {
                        'error': res['error'],
                        'result': res['result'],
                        'layout': res['layout'],
                    }
                else:
                    response = {
                        'error': 'input sound not provided',
                        'result': [],
                        'layout': [],
                    }

                return jsonify(response)

            @app.route('/stop', methods=['GET'])
            def stop():
                # yes... Flask does NOT have a shutdown function.
                os.kill(os.getpid(), signal.SIGINT)

            # use_reloader=False b/c in debug mode Flask re-executes the whole
            # script, reloading the model a second time and delaying the port
            # binding (so the requests could be answered by any older process
            # still holding the port); keep debug=True for the traceback pages
            app.run(debug=True, use_reloader=False, host='0.0.0.0', port=PORT)
            # app.run(debug=True, host='0.0.0.0', port=PORT)

        elif first_arg == 'load_model':
            response = {
                'error': '',
                'result': [],
                'layout': [],
            }
        else:
            sound_path = first_arg

            res = transcriber.transcribe(sound_path)
            response = {
                'error': res['error'],
                'result': res['result'],
                'layout': res['layout'],
            }

    print(json.dumps(response, indent=2))

    if response['error']:
        sys.exit(1)
