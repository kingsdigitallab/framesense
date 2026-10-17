# Script created by opencode:e-research/arc:apex
# Prompt: unit tests for the container bindings of the operators reading a clip file that may be
# a relative symlink to a file in the parent video folder; the video folder, not the clip folder,
# must be mounted, else the symlink does not resolve inside the container.

import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

# import the operators from the repository root, whatever the working directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from operators.answer_separators_vlm.operator import AnswerSeparatorsVLM
from operators.make_shots_scenedetect.operator import MakeShotsSceneDetect
from operators.transcode_clips_ffmpeg.operator import TranscodeClipsFFMPEG

CLIP_FOLDER_NAME = '00.00.00-62-full'
CLIP_FILE_NAME = f'{CLIP_FOLDER_NAME}.mp4'
CLIP_PATH_IN_CONTAINER = str(Path('/data') / CLIP_FOLDER_NAME / CLIP_FILE_NAME)
FFPROBE_STDOUT = '{"format": {"duration": "62.0"}}'


class _SymlinkedClipTestCase(unittest.TestCase):
    '''Common setup: a collection whose only clip file is a relative symlink to the video file in
    the parent video folder, and a recorder of the container commands instead of an actual run'''

    def setUp(self):
        self.tmp_folder = TemporaryDirectory()
        self.addCleanup(self.tmp_folder.cleanup)
        # no container engine is needed: the recorded commands are the singularity ones,
        # but no container is actually launched
        self.addCleanup(os.environ.pop, 'FRAMESENSE_CONTAINER_ENGINE', None)
        os.environ['FRAMESENSE_CONTAINER_ENGINE'] = 'singularity'

        self.collection_path = Path(self.tmp_folder.name) / 'collection'
        self.video_folder_path = self.collection_path / 'video1'
        self.video_folder_path.mkdir(parents=True)
        (self.video_folder_path / 'video1.mp4').write_bytes(b'media')

        self.clip_folder_path = self.video_folder_path / CLIP_FOLDER_NAME
        self.clip_folder_path.mkdir()
        self.clip_path = self.clip_folder_path / CLIP_FILE_NAME
        # same relative symlink as the one created by clip_full_video and separate_clips_ffmpeg
        self.clip_path.symlink_to(Path('..') / 'video1.mp4')

    def _set_context(self, operator, params=None):
        operator.set_context({
            'collections': [],
            'collections_meta': {},
            'command_args': SimpleNamespace(redo=False),
            'framesense_folder_path': Path(self.tmp_folder.name),
        })
        operator.params = params if params is not None else {}

    def _record_container_commands(self, operator):
        '''Replaces _run_command with a recorder, so that no container is launched;
        returns the list of the container commands, as lists of strings'''
        ret = []

        def record(command_args, skip=False):
            ret.append([str(a) for a in command_args])
            return subprocess.CompletedProcess(command_args, returncode=0, stdout=FFPROBE_STDOUT)

        operator._run_command = record
        return ret

    def _assert_binds_the_video_folder(self, command):
        '''Asserts that the singularity command mounts the video folder at /data, not the clip folder'''
        ret = None

        video_folder_bind = f'{self.video_folder_path.resolve()}:/data'
        clip_folder_bind = f'{self.clip_folder_path.resolve()}:/data'
        self.assertIn(video_folder_bind, command)
        self.assertNotIn(clip_folder_bind, command)
        self.assertIn(CLIP_PATH_IN_CONTAINER, command)

        return ret


class AnswerSeparatorsVlmTestCase(_SymlinkedClipTestCase):
    '''answer_separators_vlm: the ffmpeg chunk command mounts the video folder'''

    def setUp(self):
        super().setUp()
        self.operator = AnswerSeparatorsVLM()
        self._set_context(self.operator, {
            'chunk_duration_secs': 900,
            'chunk_overlap_secs': 120,
            'fps': 2,
        })
        self.commands = self._record_container_commands(self.operator)

    def test_chunk_cut_binds_the_video_folder(self):
        self.operator._make_chunk(self.clip_path, 0, 62)

        self.assertEqual(len(self.commands), 1)
        self._assert_binds_the_video_folder(self.commands[0])
        chunk_path_in_container = str(Path('/data') / CLIP_FOLDER_NAME / '_chunks' / '00000000-00000062.mp4')
        self.assertIn(chunk_path_in_container, self.commands[0])


class TranscodeClipsFfmpegTestCase(_SymlinkedClipTestCase):
    '''transcode_clips_ffmpeg: the ffmpeg command mounts the video folder'''

    def setUp(self):
        super().setUp()
        self.operator = TranscodeClipsFFMPEG()
        self._set_context(self.operator, {'command': 'ffmpeg -y -i {input} {output}.mov'})
        self.commands = self._record_container_commands(self.operator)

    def test_transcode_binds_the_video_folder(self):
        self.operator._transcode_clip(self.clip_path)

        self.assertEqual(len(self.commands), 1)
        self._assert_binds_the_video_folder(self.commands[0])


class MakeShotsScenedetectTestCase(_SymlinkedClipTestCase):
    '''make_shots_scenedetect: the scenedetect command mounts the video folder'''

    def setUp(self):
        super().setUp()
        self.operator = MakeShotsSceneDetect()
        self._set_context(self.operator, {'method': 'detect-content', 'threshold': 27})
        self.commands = self._record_container_commands(self.operator)

    def test_shots_detection_binds_the_video_folder(self):
        self.operator._make_shots(self.clip_path)

        self.assertEqual(len(self.commands), 1)
        self._assert_binds_the_video_folder(self.commands[0])
        shots_folder_in_container = str(Path('/data') / CLIP_FOLDER_NAME / 'shots.tmp')
        self.assertIn(shots_folder_in_container, self.commands[0])


if __name__ == '__main__':
    unittest.main()
