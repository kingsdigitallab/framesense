# Script created by opencode:e-research/arc:apex
# Prompt: new transcribe_vad_parakeet operator inheriting from transcribe_speech_parakeet, transcribing only the
# voice segments listed in voice_segments.json while keeping the output in the same transcription.json format.

from pathlib import Path
import json

# the parent class is imported through its module, not bound directly in this module:
# the operator discovery picks the first concrete Operator class found in the module,
# and a directly imported concrete parent (such as TranscribeSpeechParakeet)
# would shadow this operator
from ..transcribe_speech_parakeet import operator as transcribe_speech_parakeet_operator

VOICE_SEGMENTS_FILE_NAME = 'voice_segments.json'

class TranscribeVADParakeet(transcribe_speech_parakeet_operator.TranscribeSpeechParakeet):
    '''Transcribe only the voice segments of sound files into json files'''

    def _transcribe(self, clip_path: Path, collection_path: Path):
        ret = None

        sound_path = clip_path.with_suffix('.wav')
        voice_segments_path = clip_path.parent / VOICE_SEGMENTS_FILE_NAME

        if not self._is_path_selected(sound_path):
            return ret

        if not sound_path.exists():
            self._warn(f'Sound file not found: {sound_path}')
            ret = 'missing'
        elif not voice_segments_path.exists():
            self._warn(f'Voice segments not found: {voice_segments_path}')
            ret = 'missing'
        else:
            transcription_path = clip_path.parent / 'transcription.json'

            if self._is_redo() or not transcription_path.exists():
                voice_segments = self.read_json(voice_segments_path)

                if not voice_segments:
                    # no voice at all in the clip: no need to call the transcription service
                    transcription_path.write_text(json.dumps([], indent=2))
                    ret = 'created'
                else:
                    response = self._call_service_processor(sound_path, collection_path, skip=self._is_skip())

                    if response.get('error', ''):
                        ret = 'skipped'
                    elif response.get('layout') is None:
                        # only the processor of this operator returns a layout;
                        # without it the segments cannot be mapped back to the clip
                        self._warn(f'Processing service returned no layout. Input = {sound_path}')
                        ret = 'skipped'
                    else:
                        result = self._remap_result(response['result'], response['layout'])
                        transcription_path.write_text(json.dumps(result, indent=2))
                        ret = 'created'
            else:
                ret = 'existing'

        return ret

    def _get_chunk_of_segment(self, segment: dict, layout: list):
        '''Returns the layout chunk containing the middle of the segment,
        None when this middle falls into the silence inserted
        between two voice segments of the compacted sound'''
        ret = None

        middle = (segment['start'] + segment['end']) / 2

        for chunk in layout:
            if chunk['compact_start'] <= middle <= chunk['compact_end']:
                ret = chunk
                break

        return ret

    def _remap_result(self, segments: list, layout: list) -> list:
        '''Converts into the timecodes of the original clip sound the segments
        returned by the service, which are yet relative to the compacted
        voice-only sound: each segment is assigned to the voice segment which
        contains its middle, clamped within that voice segment, and dropped
        when its middle falls into the silence between two voice segments
        (hallucinated text). start_offset and end_offset are recomputed to
        index the transcript made of the returned segments joined by a single space'''
        ret = []

        start_offset = 0

        for segment in segments:
            chunk = self._get_chunk_of_segment(segment, layout)

            if chunk is not None:
                ret.append({
                    'segment': segment['segment'],
                    'start': chunk['original_start'] + max(segment['start'] - chunk['compact_start'], 0),
                    'end': chunk['original_start'] + min(segment['end'] - chunk['compact_start'], chunk['original_end'] - chunk['original_start']),
                    'start_offset': start_offset,
                    'end_offset': start_offset + len(segment['segment']),
                })

                # + 1 for the space separating two segments in the transcript
                start_offset += len(segment['segment']) + 1

        return ret
