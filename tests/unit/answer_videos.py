# Script created by opencode:e-research/arc:apex
# Prompt: unit tests for the clip walk and the per-clip answers of the answer_videos operator
# (every folder with a media file answered, clip_answers.json alongside each clip, prompt-hash
# caching and redo), plus the reading of clip_answers.json by separate_clips_ffmpeg.

import hashlib
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

# import the operators from the repository root, whatever the working directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from operators.answer_videos.operator import AnswerVideos
from operators.separate_clips_ffmpeg.operator import SeparateClipsFFMPEG

TEST_MODEL = 'm'
TEST_SEED = 3407
TEST_PROMPT_TEMPLATE = '{question}'
TEST_QUESTIONS = {'summary': {'question': 'summarise the clip'}}
TEST_PROMPT = TEST_PROMPT_TEMPLATE.replace('{question}', TEST_QUESTIONS['summary']['question'])
CLIP_FOLDER_NAME = '00.00.00-62-full'
CLIP_FILE_NAME = f'{CLIP_FOLDER_NAME}.mp4'


class _ConcreteAnswerVideos(AnswerVideos):
    '''The abstract answering operator reduced to a canned model response, recording the media it is asked about'''

    def _get_response_from_model(self, clip_path, collection_path):
        self.questioned_clip_paths.append(clip_path)
        return {
            'error': '',
            'result': '["an answer"]',
            'payload': {},
            'usage': {'total_tokens': 1},
            'stats': {'chunks': 1},
        }


def _make_media_file(path: Path) -> Path:
    '''Creates a media file with some content at the given path, its parent folders included'''
    ret = path

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'media')

    return ret


def _expected_prompt_hash() -> str:
    '''Returns the prompt hash the operator computes for the test model, seed and prompt'''
    ret = hashlib.sha256(f'{TEST_MODEL}; {TEST_SEED}; {TEST_PROMPT}'.encode('utf-8')).hexdigest()[:8]

    return ret


class _AnsweringTestCase(unittest.TestCase):
    '''Common setup: a collection with one video folder, and the params of a single question'''

    def setUp(self):
        self.operator = _ConcreteAnswerVideos()
        self.operator.questioned_clip_paths = []
        self.operator.params = {
            'model': TEST_MODEL,
            'seed': TEST_SEED,
            'prompt_template': TEST_PROMPT_TEMPLATE,
            'questions': TEST_QUESTIONS,
            'filter_questions': '',
        }

        self.tmp_folder = TemporaryDirectory()
        self.addCleanup(self.tmp_folder.cleanup)
        self.collection_path = Path(self.tmp_folder.name) / 'collection'
        self.video_folder_path = self.collection_path / 'video1'
        _make_media_file(self.video_folder_path / 'video1.mp4')

    def _set_context(self, filter='', exclude='', redo=False):
        self.operator.set_context({
            'collections': [{
                'id': 'test',
                'attributes': {'path': self.collection_path},
            }],
            'collections_meta': {},
            'command_args': SimpleNamespace(filter=filter, exclude=exclude, redo=redo),
        })

    def _seed_answers(self, clip_folder_path: Path, prompt_hash: str):
        clip_folder_path.mkdir(parents=True, exist_ok=True)
        (clip_folder_path / 'clip_answers.json').write_text(json.dumps({
            'data': {'summary': {'prompt_hash': prompt_hash}},
            'meta': {},
        }))

    def _read_answers(self, clip_folder_path: Path) -> dict:
        ret = json.loads((clip_folder_path / 'clip_answers.json').read_text())

        return ret


class ClipWalkTestCase(_AnsweringTestCase):
    '''_apply: every folder with a media file inside a video folder is answered, and nothing else'''

    def setUp(self):
        super().setUp()
        _make_media_file(self.video_folder_path / CLIP_FOLDER_NAME / CLIP_FILE_NAME)
        _make_media_file(self.video_folder_path / f'{CLIP_FOLDER_NAME}-sub' / f'{CLIP_FOLDER_NAME}-sub.mp4')
        _make_media_file(self.video_folder_path / 'chunks' / '00000000-0000062.mp4')
        (self.video_folder_path / 'leftovers').mkdir()
        (self.video_folder_path / 'leftovers' / 'notes.txt').write_text('notes')
        (self.collection_path / 'not-a-video').mkdir()
        (self.collection_path / 'stray.txt').write_text('stray')

    def test_every_folder_with_a_media_file_is_answered(self):
        self._set_context()
        self.operator._apply()

        questioned_names = [path.name for path in self.operator.questioned_clip_paths]
        self.assertEqual(questioned_names, [
            CLIP_FILE_NAME,
            f'{CLIP_FOLDER_NAME}-sub.mp4',
            '00000000-0000062.mp4',
        ])
        self.assertNotIn('video1.mp4', questioned_names)

    def test_answers_files_are_created_alongside_clips_only(self):
        self._set_context()
        self.operator._apply()

        for clip_folder_name in [CLIP_FOLDER_NAME, f'{CLIP_FOLDER_NAME}-sub', 'chunks']:
            self.assertTrue((self.video_folder_path / clip_folder_name / 'clip_answers.json').is_file())
        self.assertFalse((self.video_folder_path / 'clip_answers.json').is_file())
        self.assertFalse((self.video_folder_path / 'video_answers.json').is_file())
        self.assertFalse((self.video_folder_path / 'leftovers' / 'clip_answers.json').is_file())

    def test_answers_content(self):
        self._set_context()
        self.operator._apply()

        content = self._read_answers(self.video_folder_path / CLIP_FOLDER_NAME)
        self.assertEqual(content['meta'], {})
        self.assertEqual(content['data']['summary']['answer'], ['an answer'])
        self.assertEqual(content['data']['summary']['model'], TEST_MODEL)
        self.assertEqual(content['data']['summary']['prompt_hash'], _expected_prompt_hash())

    def test_filter_selects_clips_by_path(self):
        self._set_context(filter='-sub')
        self.operator._apply()

        questioned_names = [path.name for path in self.operator.questioned_clip_paths]
        self.assertEqual(questioned_names, [f'{CLIP_FOLDER_NAME}-sub.mp4'])


class QuestionClipTestCase(_AnsweringTestCase):
    '''_question_clip: answers file placement, prompt-hash caching and redo'''

    def setUp(self):
        super().setUp()
        self.clip_folder_path = self.video_folder_path / CLIP_FOLDER_NAME
        self.clip_path = _make_media_file(self.clip_folder_path / CLIP_FILE_NAME)

    def test_answers_file_is_created_next_to_the_clip(self):
        self._set_context()
        self.operator._question_clip(self.clip_path, self.collection_path)

        self.assertEqual(self.operator.questioned_clip_paths, [self.clip_path])
        self.assertTrue((self.clip_folder_path / 'clip_answers.json').is_file())

    def test_matching_prompt_hash_is_not_asked_again(self):
        self._seed_answers(self.clip_folder_path, _expected_prompt_hash())
        self._set_context()
        self.operator._question_clip(self.clip_path, self.collection_path)

        self.assertEqual(self.operator.questioned_clip_paths, [])

    def test_different_prompt_hash_is_asked_again(self):
        self._seed_answers(self.clip_folder_path, 'xxxxxxxx')
        self._set_context()
        self.operator._question_clip(self.clip_path, self.collection_path)

        self.assertEqual(self.operator.questioned_clip_paths, [self.clip_path])
        content = self._read_answers(self.clip_folder_path)
        self.assertEqual(content['data']['summary']['prompt_hash'], _expected_prompt_hash())

    def test_redo_asks_again_over_a_matching_prompt_hash(self):
        self._seed_answers(self.clip_folder_path, _expected_prompt_hash())
        self._set_context(redo=True)
        self.operator._question_clip(self.clip_path, self.collection_path)

        self.assertEqual(self.operator.questioned_clip_paths, [self.clip_path])

    def test_filtered_out_clip_is_not_asked(self):
        self._set_context(filter='other')
        self.operator._question_clip(self.clip_path, self.collection_path)

        self.assertEqual(self.operator.questioned_clip_paths, [])
        self.assertFalse((self.clip_folder_path / 'clip_answers.json').is_file())


class GetSeparatorsTestCase(unittest.TestCase):
    '''separate_clips_ffmpeg._get_separators: reading the sep1 answer from the clip_answers.json of the clip folder'''

    def setUp(self):
        self.operator = SeparateClipsFFMPEG()
        self.tmp_folder = TemporaryDirectory()
        self.addCleanup(self.tmp_folder.cleanup)
        self.clip_folder_path = Path(self.tmp_folder.name) / CLIP_FOLDER_NAME
        self.clip_folder_path.mkdir()

    def _write_answers(self, data: dict):
        (self.clip_folder_path / 'clip_answers.json').write_text(json.dumps({
            'data': data,
            'meta': {},
        }))

    def test_returns_the_separators_of_the_sep1_answer_of_the_clip(self):
        self._write_answers({'sep1': {'answer': [
            {'start': '00:00:05', 'end': '00:00:09', 'tag': 'bars'},
            {'start': '00:01:00', 'end': '00:01:11', 'tag': 'static'},
        ]}})
        self.assertEqual(self.operator._get_separators(self.clip_folder_path), [(5, 9), (60, 71)])

    def test_none_without_answers_file(self):
        self.assertIsNone(self.operator._get_separators(self.clip_folder_path))

    def test_none_without_sep1_answer(self):
        self._write_answers({'summary': {'answer': []}})
        self.assertIsNone(self.operator._get_separators(self.clip_folder_path))

    def test_none_with_invalid_sep1_answer(self):
        self._write_answers({'sep1': {'answer': 'not a list'}})
        self.assertIsNone(self.operator._get_separators(self.clip_folder_path))

    def test_sep1_answer_given_as_a_bare_list_is_accepted(self):
        # pre-existing behaviour: the answer is tolerated both wrapped in an object and given as a bare list
        self._write_answers({'sep1': [
            {'start': '00:00:05', 'end': '00:00:09', 'tag': 'bars'},
        ]})
        self.assertEqual(self.operator._get_separators(self.clip_folder_path), [(5, 9)])


if __name__ == '__main__':
    unittest.main()
