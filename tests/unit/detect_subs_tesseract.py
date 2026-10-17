# Script created by opencode:e-research/arc:apex
# Prompt: unit tests for the burned-in subtitle segment detection of the detect_subs_tesseract
# operator (positive sample threshold, run grouping with gap tolerance, boundary padding,
# static overlay rejection and segment filters).

import sys
import unittest
from pathlib import Path

# import the operators from the repository root, whatever the working directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from operators.detect_subs_tesseract.operator import DetectSubsTesseract

DEFAULT_PARAMS = {
    'sample_interval_secs': 2,
    'band_height': 0.25,
    'deinterlace': 1,
    'gap_tolerance_secs': 6,
    'min_segment_secs': 5,
    'min_distinct_texts': 2,
    'ocr_lang': 'eng',
    'cache_samples': 0,
}

# sample interval of the default params, the sample i being OCR-ed at i * 2 seconds
INTERVAL = 2


class GetSegmentsTestCase(unittest.TestCase):
    '''_get_segments: OCR texts of the samples to burned-in subtitle segments'''

    def setUp(self):
        self.operator = DetectSubsTesseract()
        self.operator.params = dict(DEFAULT_PARAMS)

    def _texts(self, count: int, positive_indices: set, template='Sample words {}') -> list:
        ret = [template.format(i) if i in positive_indices else '' for i in range(count)]
        return ret

    def test_no_samples_give_no_segment(self):
        self.assertEqual(self.operator._get_segments([], 100), [])

    def test_samples_without_text_give_no_segment(self):
        self.assertEqual(self.operator._get_segments(['', ' ', '...', '?'], 100), [])

    def test_one_off_sample_run_is_dropped(self):
        # a single positive sample is padded to 4 seconds, below min_segment_secs
        texts = self._texts(40, {25})
        self.assertEqual(self.operator._get_segments(texts, 100), [])

    def test_adjacent_samples_give_padded_segment(self):
        texts = self._texts(40, {25, 26})
        self.assertEqual(self.operator._get_segments(texts, 100), [{'start': 48, 'end': 54}])

    def test_gap_within_tolerance_is_bridged(self):
        texts = self._texts(40, {25, 26, 29})
        self.assertEqual(self.operator._get_segments(texts, 100), [{'start': 48, 'end': 60}])

    def test_gap_beyond_tolerance_splits_the_segments(self):
        texts = self._texts(40, {25, 26, 35, 36})
        self.assertEqual(
            self.operator._get_segments(texts, 100),
            [{'start': 48, 'end': 54}, {'start': 68, 'end': 74}],
        )

    def test_run_of_identical_texts_is_dropped(self):
        # a static overlay reads the same at every sample, subtitles do not
        texts = self._texts(40, set(range(20, 30)), template='STATIC OVERLAY')
        self.assertEqual(self.operator._get_segments(texts, 100), [])

    def test_run_of_two_distinct_texts_is_kept(self):
        texts = ['' for _ in range(40)]
        for i in range(20, 30):
            texts[i] = 'STATIC OVERLAY' if i % 2 else 'OTHER OVERLAY'
        self.assertEqual(self.operator._get_segments(texts, 100), [{'start': 38, 'end': 60}])

    def test_boundaries_are_clamped_to_the_clip(self):
        texts = self._texts(52, {0, 1, 2, 48, 49})
        self.assertEqual(
            self.operator._get_segments(texts, 100),
            [{'start': 0, 'end': 6}, {'start': 94, 'end': 100}],
        )

    def test_min_distinct_texts_parameter(self):
        self.operator.params['min_distinct_texts'] = 3
        texts = self._texts(40, {25, 26})
        self.assertEqual(self.operator._get_segments(texts, 100), [])

    def test_min_segment_secs_parameter(self):
        self.operator.params['min_segment_secs'] = 10
        texts = self._texts(40, {25, 26, 27})
        self.assertEqual(self.operator._get_segments(texts, 100), [])
        texts = self._texts(40, {25, 26, 27, 28, 29})
        self.assertEqual(self.operator._get_segments(texts, 100), [{'start': 48, 'end': 60}])

    def test_non_integer_interval_gives_float_segment(self):
        self.operator.params['sample_interval_secs'] = 1.5
        texts = self._texts(30, {10, 11, 12})
        self.assertEqual(self.operator._get_segments(texts, 100), [{'start': 13.5, 'end': 19.5}])


class NormalizeTextTestCase(unittest.TestCase):
    '''_normalize_text: lowercased alphanumeric text for positive detection and duplicate comparison'''

    def setUp(self):
        self.operator = DetectSubsTesseract()
        self.operator.params = dict(DEFAULT_PARAMS)

    def test_punctuation_is_stripped(self):
        self.assertEqual(self.operator._normalize_text('Well, hello!'), 'well hello')

    def test_non_alphanumeric_characters_are_dropped(self):
        self.assertEqual(self.operator._normalize_text('ÜBER? no*'), 'ber no')

    def test_single_character_is_below_positive_threshold(self):
        self.assertLess(len(self.operator._normalize_text('a?')), 2)


class GetSampleFilterTestCase(unittest.TestCase):
    '''_get_sample_filter: the FFMPEG filter chain sampling the subtitle band of the clip'''

    def setUp(self):
        self.operator = DetectSubsTesseract()
        self.operator.params = dict(DEFAULT_PARAMS)

    def test_default_filter(self):
        self.assertEqual(
            self.operator._get_sample_filter(),
            f'yadif,fps=1/{INTERVAL},crop=iw:ih*0.25:0:ih*(1-0.25),scale=640:-2,format=gray',
        )

    def test_deinterlace_can_be_disabled(self):
        self.operator.params['deinterlace'] = 0
        self.assertNotIn('yadif', self.operator._get_sample_filter())


if __name__ == '__main__':
    unittest.main()
