from pathlib import Path
from abc import ABC, abstractmethod
from ..base.operator import Operator
import re
import json
import datetime
import hashlib

class AnswerVideos(Operator, ABC):
    '''Let a VLM answer questions about a video'''

    def get_supported_arguments(self):
        ret = super().get_supported_arguments()
        ret['redo'] = True
        ret['filter'] = True
        return ret

    def _apply(self):
        ret = None

        for col in self.context['collections']:
            collection_path = col['attributes']['path']
            for video_folder_path in collection_path.iterdir():
                video_path = self._get_video_file_path(video_folder_path, direct_child_only=True)
                if video_path is None: 
                    continue
                self._question_video(video_path, collection_path)

        return ret

    def _question_video(self, video_path: Path, collection_path: Path, unit='video'):
        if not self._is_path_selected(video_path):
            return

        video_answers_path = video_path.parent / f'{unit}_answers.json'

        answers_file_content = self._read_data_file(video_answers_path, is_data_dict=True)
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
                   self.get_param('max_new_tokens'),
                   prompt
                ]
            ]))

            if not self._is_redo() and answers.get(question_key, {}).get('prompt_hash', None) == prompt_hash:
                # we already got that answer, skip
                continue

            # pass the prompt to the container
            self.set_param('prompt', prompt)

            prompt_length = len(re.findall(r'\w+', prompt))
            self._log(f'{video_path} (question: {question_key}; words in prompt: {prompt_length})')

            response = self._get_response_from_model(video_path, collection_path)           

            if response['error']:
                self._error(response['error'])

            answer = response['result']

            answers[question_key] = {
                'answer': self._parse_dirty_json(answer),
                'model': self.get_param('model'),
                'options': response.get('options', {}),
                'updated': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'prompt_hash': prompt_hash,
                'stats': response.get('stats', {}),
                'usage': response.get('usage', {})
            }
        
            self._write_data_file(video_answers_path, answers_file_content)

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
    def _get_response_from_model(self, video_path, collection_path):
        raise NotImplementedError
