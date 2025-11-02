from pathlib import Path
from ..base.operator import Operator
import re
import json
import datetime
import hashlib

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

        answers_file_content = self._read_data_file(transcript_answers_path, is_data_dict=True)
        answers = answers_file_content['data']
        
        template = self.get_param('prompt_template')
        questions = self.get_param('questions')

        transcription = self.read_json(transcription_path)
        transcription_srt = '\n'.join([
            f'{self.get_hhmmss(item["start"])} {item["segment"]}'
            for item in transcription
        ])

        for question_key, question in questions.items():
            prompt = template
            prompt = prompt.replace('{transcription}', transcription_srt)
            prompt = prompt.replace('{question}', question['question'])

            prompt_hash = self.short_hash(f'{self.get_param('model')}; {self.get_param('context_length')}; {prompt}')

            if not self._is_redo() and answers.get(question_key, {}).get('prompt_hash', None) == prompt_hash:
                # we already got that answer, skip
                continue

            # pass the prompt to the container
            self.set_param('prompt', prompt)

            prompt_length = len(re.findall(r'\w+', prompt))
            self._log(f'{transcription_path} (question: {question_key}; words in prompt: {prompt_length})')

            binding = [clip_path.parent, Path('/data')]
            command_args = [
                'python', 
                '/app/processor.py',
                'answer'
            ]
            res = self._run_in_operator_container(command_args, binding, share_network=True)
            response = json.loads(res.stdout)
            # TODO: check for errors
            answer = response['result']

            answers[question_key] = {
                'answer': self._parse_dirty_json(answer),
                'model': self.get_param('model'),
                'context_length': self.get_param('context_length'),
                'updated': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'prompt_hash': prompt_hash,
            }

        
        # if not self._is_redo():
        #     # TODO: better method: remove all questions which are already answered
        #     if answers_file_content['data']:
        #         return

        self._write_data_file(transcript_answers_path, answers_file_content)

    def short_hash(self, s, length=8):
        hash_object = hashlib.sha256(s.encode('utf-8'))
        return hash_object.hexdigest()[:length]


    def get_hhmmss(self, seconds):
        hours = int(seconds // 3600)
        seconds %= 3600
        minutes = int(seconds // 60)
        seconds %= 60
        return f"{hours:02d}:{minutes:02d}:{int(seconds):02d}"
