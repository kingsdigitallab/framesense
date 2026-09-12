# Script created by opencode:e-research/arc:apex
# Prompt: parse a clip's *.wav file with silero-vad and return the segments (start, end timecodes in seconds)
# where a voice is detected; used by detect_speech_vad to save them into voice_segments.json.

from silero_vad import load_silero_vad, read_audio, get_speech_timestamps
from pathlib import Path
import sys
import json
from flask import Flask, request, jsonify
import signal
import os

PARAMS = json.loads((Path(__file__).parent / 'params.json').read_text())

PORT = 5000
SAMPLING_RATE = 16000

'''
Usage:

1. Single detection from command line:

`python processor.py /path/to/my/sound.wav`

2. Bulk detection from a http service:

2.1 load the model and service

`python processor.py serve`

2.2 call the service

`curl localhost:5000/process?input_path=/path/to/my/sound.wav`

2.3 stop the service

`curl localhost:5000/stop`

In all cases responses are in json:

on success:

{
    "error": "",
    "result": [
        {
            "start": 4.96,
            "end": 9.28
        },
    ]
}

on failure:

{
    "error": "ERROR MESSAGE",
    "result": []
}

'''


class Detector:
    '''Voice activity detector wrapping the silero-vad model'''

    def __init__(self):
        self.model = load_silero_vad()

    def detect(self, sound_path):
        sound_path = Path(sound_path)

        wav = read_audio(str(sound_path), sampling_rate=SAMPLING_RATE)

        speech_timestamps = get_speech_timestamps(
            wav,
            self.model,
            sampling_rate=SAMPLING_RATE,
            return_seconds=True,
            threshold=PARAMS['threshold'],
            min_silence_duration_ms=PARAMS['min_silence_duration_ms'],
        )

        return speech_timestamps


if __name__ == '__main__':
    response = {
        'error': 'input sound not provided',
        'result': [],
    }

    # read the sound file name from the first command line argument
    arguments = sys.argv

    if len(arguments) > 1:
        first_arg = arguments[1]

        detector = Detector()

        if first_arg == 'serve':
            app = Flask(__name__)

            @app.route('/process', methods=['GET'])
            def detect():
                sound_path = request.args.get('input_path', None)

                if sound_path:
                    res = detector.detect(sound_path)
                    response = {
                        'error': '',
                        'result': res,
                    }
                else:
                    response = {
                        'error': 'input sound not provided',
                        'result': [],
                    }

                return jsonify(response)

            @app.route('/stop', methods=['GET'])
            def stop():
                # yes... Flask does NOT have a shutdown function.
                os.kill(os.getpid(), signal.SIGINT)

            app.run(debug=True, host='0.0.0.0', port=PORT)
        elif first_arg == 'load_model':
            response = {
                'error': '',
                'result': [],
            }
        else:
            sound_path = first_arg

            res = detector.detect(sound_path)
            response = {
                'error': '',
                'result': res,
            }

    print(json.dumps(response, indent=2))

    if response['error']:
        sys.exit(1)
