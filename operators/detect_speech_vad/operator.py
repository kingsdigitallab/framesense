# Script created by opencode:e-research/arc:apex
# Prompt: create a new operator detect_speech_vad which uses silero-vad to parse a clip's *.wav file
# and save in voice_segments.json an array of segments (start, end timecodes in seconds) where a voice is detected.

from pathlib import Path
from ..base.operator import Operator
import json

# name of the file where the voice segments are saved in the clip folder
VOICE_SEGMENTS_FILE_NAME = 'voice_segments.json'


class DetectSpeechVAD(Operator):
    '''Detect voice segments in sound files using silero-vad'''

    def get_supported_arguments(self):
        ret = super().get_supported_arguments()
        ret['redo'] = True
        ret['filter'] = True
        ret['skip'] = True
        return ret

    def _apply(self):
        ret = None

        stats = {
            'created': 0,
            'existing': 0,
            'skipped': 0,
            'missing': 0,
        }

        for col in self.context['collections']:
            collection_path = col['attributes']['path']
            for video_folder_path in col['attributes']['path'].iterdir():
                if video_folder_path.is_dir():
                    for clip_folder_path in video_folder_path.iterdir():
                        if clip_folder_path.is_dir():
                            clip_path = self._get_video_file_path(clip_folder_path)
                            if clip_path:
                                outcome = self._detect(clip_path, collection_path)
                                if outcome:
                                    stats[outcome] += 1

        self._log(f"voice segment files created: {stats['created']}; already existing: {stats['existing']}; clips skipped: {stats['skipped']}; sound files not found: {stats['missing']}")

        return ret

    def _detect(self, clip_path: Path, collection_path: Path):
        ret = None

        sound_path = clip_path.with_suffix('.wav')

        if not self._is_path_selected(sound_path):
            return ret

        if not sound_path.exists():
            self._warn(f'Input sound not found: {sound_path}')
            ret = 'missing'
        else:
            voice_segments_path = clip_path.parent / VOICE_SEGMENTS_FILE_NAME

            if self._is_redo() or not voice_segments_path.exists():
                response = self._call_service_processor(sound_path, collection_path, skip=self._is_skip())

                if response.get('error', ''):
                    ret = 'skipped'
                else:
                    voice_segments_path.write_text(json.dumps(response['result'], indent=2))
                    ret = 'created'
            else:
                ret = 'existing'

        return ret
