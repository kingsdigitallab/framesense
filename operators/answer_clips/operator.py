from pathlib import Path
from abc import ABC, abstractmethod
from ..base.operator import Operator
import re
import json
import datetime
import hashlib

class AnswerClips(Operator, ABC):
    '''Let a VLM answer questions about a clip'''

    def get_supported_arguments(self):
        ret = super().get_supported_arguments()
        ret['redo'] = True
        ret['filter'] = True
        return ret

    def _apply(self):
        ret = None

        for col in self.context['collections']:
            collection_path = col['attributes']['path']
            for video_folder_path in sorted(collection_path.iterdir()):
                if not video_folder_path.is_dir():
                    continue
                for clip_folder_path in sorted(video_folder_path.iterdir()):
                    if not clip_folder_path.is_dir():
                        continue
                    clip_path = self._get_video_file_path(clip_folder_path, direct_child_only=True)
                    if clip_path is None:
                        continue
                    self._question_clip(clip_path, collection_path)

        return ret

    def _question_clip(self, clip_path: Path, collection_path: Path, unit='clip'):
        if not self._is_path_selected(clip_path):
            return

        clip_answers_path = clip_path.parent / f'{unit}_answers.json'

        answers_file_content = self._read_data_file(clip_answers_path, is_data_dict=True)
        answers = answers_file_content['data']

        template = self.get_param('prompt_template')
        questions = self.get_param('questions')

        filter_questions = self.get_param('filter_questions', '').split(',')
        filter_questions = [q.strip() for q in filter_questions if q.strip()]

        for question_key, question in questions.items():
            if filter_questions and question_key not in filter_questions:
                continue

            prompt = template
            prompt = prompt.replace('{question}', question['question'])

            prompt_hash = self.short_hash('; '.join([
                str(p)
                for p
                in [
                   self.get_param('model'), 
                   self.get_param('seed'),
                   prompt
                ]
            ]))

            if not self._is_redo() and answers.get(question_key, {}).get('prompt_hash', None) == prompt_hash:
                # we already got that answer, skip
                continue

            # pass the prompt to the container
            self.set_param('prompt', prompt)

            prompt_length = len(re.findall(r'\w+', prompt))
            self._log(f'{clip_path} (question: {question_key}; words in prompt: {prompt_length})')

            response = self._get_response_from_model(clip_path, collection_path)           

            if response['error']:
                self._error(response['error'])

            answer = response['result']

            answers[question_key] = {
                'answer': self._parse_dirty_json(answer),
                'model': self.get_param('model'),
                'options': response.get('payload', {}),
                'updated': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'prompt_hash': prompt_hash,
                'stats': response.get('stats', {}),
                'usage': response.get('usage', {})
            }
        
            self._write_data_file(clip_answers_path, answers_file_content)

    def short_hash(self, s, length=8):
        hash_object = hashlib.sha256(s.encode('utf-8'))
        return hash_object.hexdigest()[:length]


    def get_hhmmss(self, seconds):
        hours = int(seconds // 3600)
        seconds %= 3600
        minutes = int(seconds // 60)
        seconds %= 60
        return f"{hours:02d}:{minutes:02d}:{int(seconds):02d}"

    @abstractmethod
    def _get_response_from_model(self, clip_path, collection_path):
        raise NotImplementedError
