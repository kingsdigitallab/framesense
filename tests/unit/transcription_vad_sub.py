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


class SplitLongSegmentsTestCase(unittest.TestCase):
    '''_split_text, _split_cue, _split_cues and _merge_tiny_cues'''

    def setUp(self):
        self.operator = _ConcreteOperator()
        self.operator.params = {'split_long_segments': 1}

    def test_split_text_splits_at_sentence_boundaries(self):
        self.assertEqual(self.operator._split_text('One. Two. Three.'), ['One.', 'Two.', 'Three.'])

    def test_split_text_wraps_too_long_sentences(self):
        text = 'The quick brown fox jumps over the lazy dog and runs away quickly to the woods deep down the hill every single evening.'
        pieces = self.operator._split_text(text)
        self.assertGreater(len(pieces), 1)
        self.assertTrue(all(len(piece) <= 42 for piece in pieces))
        self.assertEqual(' '.join(piece for piece in pieces), text)

    def test_split_text_respects_max_cue_chars_parameter(self):
        self.operator.params['max_cue_chars'] = 20
        pieces = self.operator._split_text('The quick brown fox jumps over the lazy dog and runs away quickly.')
        self.assertTrue(all(len(piece) <= 20 for piece in pieces))

    def test_split_cue_keeps_unchanged_short_items(self):
        item = {'start': 10, 'end': 12, 'segment': 'Hello.'}
        self.assertEqual(self.operator._split_cue(item), [item])

    def test_split_cue_distributes_time_proportionally(self):
        item = {'start': 10, 'end': 20, 'segment': 'Aaa. Bbbb.'}
        pieces = self.operator._split_cue(item)
        self.assertEqual([p['segment'] for p in pieces], ['Aaa.', 'Bbbb.'])
        self.assertAlmostEqual(pieces[0]['start'], 10)
        self.assertAlmostEqual(pieces[-1]['end'], 20)
        self.assertEqual([p['end'] - p['start'] for p in pieces], [10 * 4 / 9, 10 * 5 / 9])
        self.assertTrue(all(p['start'] < p['end'] for p in pieces))

    def test_split_cues_passthrough_when_disabled(self):
        self.operator.params = {}
        items = [{'start': 0, 'end': 10, 'segment': 'One. Two. Three Four Five Six Seven Eight Nine Ten.'}]
        self.assertEqual(self.operator._split_cues(items), (items, 0))

    def test_split_cues_splits_and_counts_when_enabled(self):
        items = [
            {'start': 0, 'end': 10, 'segment': 'One. Two. Three Four Five Six Seven Eight Nine Ten Eleven Twelve.'},
            {'start': 10, 'end': 11, 'segment': 'Short.'},
        ]
        cues, split_count = self.operator._split_cues(items)
        self.assertEqual(split_count, 1)
        self.assertGreater(len(cues), len(items))

    def test_merge_tiny_cues_merges_into_previous(self):
        cues = [{'start': 10, 'end': 12, 'segment': 'This is a normal sized subtitle piece.'},
                {'start': 12, 'end': 13, 'segment': 'Yes.'}]
        merged = self.operator._merge_tiny_cues(cues)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]['segment'], 'This is a normal sized subtitle piece. Yes.')
        self.assertEqual(merged[0]['start'], 10)
        self.assertEqual(merged[0]['end'], 13)

    def test_merge_tiny_cues_merges_leading_cue_forward(self):
        cues = [{'start': 10, 'end': 11, 'segment': 'Yes.'},
                {'start': 11, 'end': 13, 'segment': 'This is a normal sized subtitle piece.'}]
        merged = self.operator._merge_tiny_cues(cues)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]['segment'], 'Yes. This is a normal sized subtitle piece.')
        self.assertEqual(merged[0]['start'], 10)
        self.assertEqual(merged[0]['end'], 13)

    def test_merge_tiny_cues_keeps_two_lines_short(self):
        long_cue = 'This is a subtitle piece almost reaching the two lines limit of the subtitle player.'
        self.assertEqual(len(long_cue), 84)
        cues = [{'start': 10, 'end': 12, 'segment': long_cue},
                {'start': 12, 'end': 13, 'segment': 'Yes.'}]
        merged = self.operator._merge_tiny_cues(cues)
        self.assertEqual(len(merged), 2)

    def test_merge_tiny_cues_passthrough_when_disabled(self):
        self.operator.params = {}
        cues = [{'start': 10, 'end': 12, 'segment': 'This is a normal sized subtitle piece.'},
                {'start': 12, 'end': 13, 'segment': 'Yes.'}]
        self.assertEqual(self.operator._merge_tiny_cues(cues), cues)

    def test_merge_tiny_cues_does_not_mutate_input(self):
        cues = [{'start': 10, 'end': 12, 'segment': 'This is a normal sized subtitle piece.'},
                {'start': 12, 'end': 13, 'segment': 'Yes.'}]
        self.operator._merge_tiny_cues(cues)
        self.assertEqual(cues[0]['segment'], 'This is a normal sized subtitle piece.')
        self.assertEqual(cues[1]['segment'], 'Yes.')

    def test_split_before_filter_drops_hallucinated_tail(self):
        transcription = [{'start': 0, 'end': 10, 'segment': 'Genuine speech at the start of the clip. The hallucinated tail of the segment is on silence.'}]
        voice_segments = [{'start': 0.2, 'end': 3.0}]
        over_duration = 3.0 - 0.2
        split_cues, _ = self.operator._split_cues(transcription)
        self.assertGreater(len(split_cues), 1)
        kept = [cue for cue in split_cues if self.operator._get_max_overlap(cue, voice_segments) > 0]
        kept = [cue for cue in kept if self.operator._is_speech(cue, voice_segments)]
        merged = self.operator._merge_tiny_cues(kept)
        self.assertEqual(' '.join(c['segment'] for c in merged), 'Genuine speech at the start of the clip.')
        self.assertGreater(over_duration, 0.25)
        self.assertEqual(self.operator._get_max_overlap(transcription[0], voice_segments), over_duration)
        self.assertTrue(self.operator._is_speech(transcription[0], voice_segments))


if __name__ == '__main__':
    unittest.main()