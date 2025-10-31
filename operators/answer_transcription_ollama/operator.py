from pathlib import Path
from ..base.operator import Operator
import re
import json
from datetime import datetime
import subprocess
import shutil

class AnswerTranscriptionOllama(Operator):
    '''Let a LLM served by Ollama answer a question about a transcription'''

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
                                self._question_transcription(clip_path, collection_path)

        return ret

    def _question_transcription(self, clip_path: Path, collection_path: Path):
        transcription_path = clip_path.parent / 'transcription.json'

        if not self._is_path_selected(transcription_path):
            return

        if not transcription_path.exists():
            self._warn(f'Input transcription not found: {transcription_path}')
            return

        transcript_answers_path = transcription_path.parent / 'transcription_answers.json'

        if self._is_redo() or not transcript_answers_path.exists():
            self._log(transcription_path)
            # self._log(transcription_srt)

            if 0:
                question = f'''Return a JSON Array with all the place names mentioned 
                in the video transcription that follows.

                Video transcription:
                '''
                res = self._call_service_processor(sound_path, collection_path)
                transcription_path.write_text(json.dumps(res, indent=2))

            binding = [clip_path.parent, Path('/data')]
            command_args = [
                'python', 
                '/app/processor.py',
                transcription_path
            ]
            res = self._run_in_operator_container(command_args, binding, share_network=True)
            response = json.loads(res.stdout)
            answer = response['result']
            print(answer)

