# Script created by opencode:e-research/arc:apex
# Prompt: unit tests for the hallucination filters of the transcription_vad_sub operator
# (short-overlap speech test, stale srt detection and consecutive-duplicate collapsing).

import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

# import the operator from the repository root, whatever the working directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from operators.transcription_vad_sub.operator import TranscriptionVADSub


class _ConcreteOperator(TranscriptionVADSub):
    '''The abstract base operator reduced to what the filters need to run'''

    def _apply(self):
        return None


class OverlapTestCase(unittest.TestCase):
    '''_get_max_overlap and _is_speech'''

    def setUp(self):
        self.operator = _ConcreteOperator()
        self.operator.params = {}
        self.voice_segments = [{'start': 10, 'end': 20}]

    def test_no_overlap_gives_zero(self):
        self.assertEqual(self.operator._get_max_overlap({'start': 0, 'end': 9}, self.voice_segments), 0)

    def test_partial_overlap(self):
        self.assertEqual(self.operator._get_max_overlap({'start': 5, 'end': 15}, self.voice_segments), 5)

    def test_full_overlap(self):
        self.assertEqual(self.operator._get_max_overlap({'start': 11, 'end': 19}, self.voice_segments), 8)

    def test_max_overlap_across_segments(self):
        voice_segments = [{'start': 10, 'end': 12}, {'start': 20, 'end': 25}]
        self.assertEqual(self.operator._get_max_overlap({'start': 11, 'end': 21}, voice_segments), 1)

    def test_overlap_below_minimum_is_not_speech(self):
        item = {'start': 19.85, 'end': 20.1}
        self.assertAlmostEqual(self.operator._get_max_overlap(item, self.voice_segments), 0.15)
        self.assertFalse(self.operator._is_speech(item, self.voice_segments))

    def test_overlap_at_least_minimum_is_speech(self):
        item = {'start': 19.7, 'end': 20.1}
        self.assertAlmostEqual(self.operator._get_max_overlap(item, self.voice_segments), 0.3)
        self.assertTrue(self.operator._is_speech(item, self.voice_segments))

    def test_min_overlap_seconds_parameter(self):
        self.operator.params['min_overlap_seconds'] = 0.1
        item = {'start': 19.85, 'end': 20.1}
        self.assertTrue(self.operator._is_speech(item, self.voice_segments))


class StaleTestCase(unittest.TestCase):
    '''_is_stale decision based on file modification times'''

    def setUp(self):
        self.operator = _ConcreteOperator()
        self.operator.params = {}
        self.tmp_folder = TemporaryDirectory()
        self.addCleanup(self.tmp_folder.cleanup)
        self.folder = Path(self.tmp_folder.name)

    def _touch(self, path: Path, mtime: float) -> Path:
        path.write_text('content')
        os.utime(path, (mtime, mtime))
        return path

    def test_older_srt_is_stale(self):
        srt_path = self._touch(self.folder / 'clip.srt', 100)
        transcription_path = self._touch(self.folder / 'transcription.json', 200)
        voice_segments_path = self.folder / 'voice_segments.json'
        self.assertTrue(self.operator._is_stale(srt_path, transcription_path, voice_segments_path))

    def test_newer_srt_is_not_stale(self):
        srt_path = self._touch(self.folder / 'clip.srt', 200)
        transcription_path = self._touch(self.folder / 'transcription.json', 100)
        voice_segments_path = self.folder / 'voice_segments.json'
        self.assertFalse(self.operator._is_stale(srt_path, transcription_path, voice_segments_path))

    def test_new_voice_segments_make_srt_stale(self):
        srt_path = self._touch(self.folder / 'clip.srt', 150)
        transcription_path = self._touch(self.folder / 'transcription.json', 100)
        voice_segments_path = self._touch(self.folder / 'voice_segments.json', 200)
        self.assertTrue(self.operator._is_stale(srt_path, transcription_path, voice_segments_path))

    def test_missing_voice_segments_are_ignored(self):
        srt_path = self._touch(self.folder / 'clip.srt', 200)
        transcription_path = self._touch(self.folder / 'transcription.json', 100)
        voice_segments_path = self.folder / 'voice_segments.json'
        self.assertFalse(self.operator._is_stale(srt_path, transcription_path, voice_segments_path))


class CollapseRepeatsTestCase(unittest.TestCase):
    '''_collapse_repeats and _normalize'''

    def setUp(self):
        self.operator = _ConcreteOperator()
        self.operator.params = {}

    def _cues(self, segments):
        ret = []
        for i, segment in enumerate(segments):
            ret.append({'start': i, 'end': i + 1, 'segment': segment})
        return ret

    def test_single_cues_are_unchanged(self):
        cues = self._cues(['Hello.', 'World.'])
        self.assertEqual([c['segment'] for c in self.operator._collapse_repeats(cues)], ['Hello.', 'World.'])

    def test_short_run_is_kept(self):
        cues = self._cues(['Yes.', 'Yes.'])
        self.assertEqual([c['segment'] for c in self.operator._collapse_repeats(cues)], ['Yes.', 'Yes.'])

    def test_long_run_is_collapsed_to_single_cue(self):
        cues = self._cues(["I don't know."] * 5)
        self.assertEqual([c['segment'] for c in self.operator._collapse_repeats(cues)], ["I don't know."])

    def test_only_consecutive_runs_are_collapsed(self):
        cues = self._cues(["I don't know.", 'Real speech.', "I don't know.", "I don't know.", "I don't know."])
        self.assertEqual(
            [c['segment'] for c in self.operator._collapse_repeats(cues)],
            ["I don't know.", 'Real speech.', "I don't know."],
        )

    def test_case_and_punctuation_are_normalized(self):
        cues = self._cues(['I\'m going!', 'Im going', 'i\'m going'])
        self.assertEqual([c['segment'] for c in self.operator._collapse_repeats(cues)], ['I\'m going!'])

    def test_max_repeat_run_parameter(self):
        self.operator.params['max_repeat_run'] = 4
        cues = self._cues(['Yes.'] * 3)
        self.assertEqual([c['segment'] for c in self.operator._collapse_repeats(cues)], ['Yes.'] * 3)

    def test_max_repeat_run_one_collapses_everything(self):
        self.operator.params['max_repeat_run'] = 1
        cues = self._cues(['A.', 'B.'])
        self.assertEqual([c['segment'] for c in self.operator._collapse_repeats(cues)], ['A.', 'B.'])

    def test_normalize(self):
        self.assertEqual(self.operator._normalize("Well, I'm 90% sure!"), 'well im 90 sure')
        self.assertEqual(self.operator._normalize('   UPPER Case -- . , '), 'upper case')


if __name__ == '__main__':
    unittest.main()