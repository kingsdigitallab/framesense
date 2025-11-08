from pathlib import Path
from ..base.operator import Operator
import json

# https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2

class TranscribeSpeechParakeet(Operator):
    '''Transcribe speech from sound files into json files'''

    def get_supported_arguments(self):
        ret = super().get_supported_arguments()
        ret['redo'] = True
        ret['filter'] = True
        return ret

    def _apply(self):
        ret = None

        for col in self.context['collections']:
            collection_path = col['attributes']['path']
            for video_folder_path in col['attributes']['path'].iterdir():
                if video_folder_path.is_dir():
                    for clip_folder_path in video_folder_path.iterdir():
                        if clip_folder_path.is_dir():
                            clip_path = self._get_video_file_path(clip_folder_path)
                            if clip_path:
                                self._transcribe(clip_path, collection_path)

        return ret

    def _transcribe(self, clip_path: Path, collection_path: Path):
        sound_path = clip_path.with_suffix('.wav')

        if not self._is_path_selected(sound_path):
            return

        if not sound_path.exists():
            self._warn(f'Input transcription not found: {sound_path}')
            return

        transcription_path = clip_path.parent / 'transcription.json'

        if self._is_redo() or not transcription_path.exists():
            # self._log(transcription_path)
            response = self._call_service_processor(sound_path, collection_path)
            transcription_path.write_text(json.dumps(response['result'], indent=2))

