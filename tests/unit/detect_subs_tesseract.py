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
    'min_word_conf': 60,
    'subtitle_band_top': 0.5,
    'subtitle_band_bottom': 0.9,
    'edge_margin': 0.1,
    'min_word_height': 0.12,
    'max_word_height': 0.6,
    'max_baseline_drift': 0.1,
    'use_word_geometry': 1,
    'use_temporal_consistency': 1,
    'ocr_lang': 'eng',
    'cache_samples': 0,
}

# sample interval of the default params, the sample i being OCR-ed at i * 2 seconds
INTERVAL = 2
# geometry of the samples, matching SAMPLE_WIDTH x SAMPLE_HEIGHT of the operator
SAMPLE_WIDTH = 640
SAMPLE_HEIGHT = 120


def word(text, top=70, left=250, width=140, height=30, conf=90):
    '''A tesseract word box centred on the subtitle line by default'''
    return {'text': text, 'top': top, 'left': left, 'width': width, 'height': height, 'conf': conf}


def centered_word(text, index):
    '''A clean, high-confidence word centred horizontally on the subtitle line'''
    return word(text, left=200 + index * 80)


class GetSegmentsTestCase(unittest.TestCase):
    '''_get_segments: word boxes of the samples to burned-in subtitle segments'''

    def setUp(self):
        self.operator = DetectSubsTesseract()
        self.operator.params = dict(DEFAULT_PARAMS)

    def _samples(self, count: int, positive_indices: set, template='Sample words {}') -> list:
        '''One sample of two clean subtitle words at each positive index, empty samples elsewhere'''
        ret = []
        for i in range(count):
            if i in positive_indices:
                ret.append([centered_word(template.format(i), 0), centered_word('again', 1)])
            else:
                ret.append([])
        return ret

    def test_no_samples_give_no_segment(self):
        self.assertEqual(self.operator._get_segments([], 100), [])

    def test_samples_without_text_give_no_segment(self):
        self.assertEqual(self.operator._get_segments([[], [], []], 100), [])

    def test_one_off_sample_run_is_dropped(self):
        # a single positive sample is padded to 4 seconds, below min_segment_secs
        samples = self._samples(40, {25})
        self.assertEqual(self.operator._get_segments(samples, 100), [])

    def test_adjacent_samples_give_padded_segment(self):
        samples = self._samples(40, {25, 26})
        self.assertEqual(self.operator._get_segments(samples, 100), [{'start': 48, 'end': 54}])

    def test_gap_within_tolerance_is_bridged(self):
        samples = self._samples(40, {25, 26, 29})
        self.assertEqual(self.operator._get_segments(samples, 100), [{'start': 48, 'end': 60}])

    def test_gap_beyond_tolerance_splits_the_segments(self):
        samples = self._samples(40, {25, 26, 35, 36})
        self.assertEqual(
            self.operator._get_segments(samples, 100),
            [{'start': 48, 'end': 54}, {'start': 68, 'end': 74}],
        )

    def test_run_of_identical_texts_is_dropped(self):
        # a static overlay reads the same at every sample, subtitles do not
        samples = self._samples(40, set(range(20, 30)), template='STATIC OVERLAY')
        self.assertEqual(self.operator._get_segments(samples, 100), [])

    def test_run_of_two_distinct_texts_is_kept(self):
        samples = [[] for _ in range(40)]
        for i in range(20, 30):
            text = 'STATIC OVERLAY' if i % 2 else 'OTHER OVERLAY'
            samples[i] = [centered_word(text, 0), centered_word('again', 1)]
        self.assertEqual(self.operator._get_segments(samples, 100), [{'start': 38, 'end': 60}])

    def test_boundaries_are_clamped_to_the_clip(self):
        samples = self._samples(52, {0, 1, 2, 48, 49})
        self.assertEqual(
            self.operator._get_segments(samples, 100),
            [{'start': 0, 'end': 6}, {'start': 94, 'end': 100}],
        )

    def test_min_distinct_texts_parameter(self):
        self.operator.params['min_distinct_texts'] = 3
        samples = self._samples(40, {25, 26})
        self.assertEqual(self.operator._get_segments(samples, 100), [])

    def test_min_segment_secs_parameter(self):
        self.operator.params['min_segment_secs'] = 10
        samples = self._samples(40, {25, 26, 27})
        self.assertEqual(self.operator._get_segments(samples, 100), [])
        samples = self._samples(40, {25, 26, 27, 28, 29})
        self.assertEqual(self.operator._get_segments(samples, 100), [{'start': 48, 'end': 60}])

    def test_non_integer_interval_gives_float_segment(self):
        self.operator.params['sample_interval_secs'] = 1.5
        samples = self._samples(30, {10, 11, 12})
        self.assertEqual(self.operator._get_segments(samples, 100), [{'start': 13.5, 'end': 19.5}])

    def test_scene_text_reaching_the_edges_is_rejected(self):
        # negative regression: a sign at the frame edge, read over a long run, is not a subtitle
        samples = [[] for _ in range(40)]
        for i in range(20, 30):
            samples[i] = [word(f'WINVINLANDY {i}', left=0, width=200)]
        self.assertEqual(self.operator._get_segments(samples, 100), [])

    def test_low_confidence_noise_is_rejected(self):
        samples = [[] for _ in range(40)]
        for i in range(20, 30):
            samples[i] = [word(f'noise {i}', conf=20)]
        self.assertEqual(self.operator._get_segments(samples, 100), [])

    def test_baseline_drift_beyond_tolerance_is_rejected(self):
        # scene text wandering vertically with the camera, not subtitles on a fixed line
        samples = [[] for _ in range(40)]
        for i, top in enumerate(range(62, 108, 5)):
            samples[20 + i] = [word(f'wandering {i}', top=top)]
        self.assertEqual(self.operator._get_segments(samples, 100), [])

    def test_word_geometry_can_be_disabled(self):
        self.operator.params['use_word_geometry'] = 0
        # with the geometry filter off, the edge sign words are kept and the run is a segment
        samples = [[] for _ in range(40)]
        for i in range(20, 30):
            samples[i] = [word(f'WINVINLANDY {i}', left=0, width=200)]
        self.assertEqual(self.operator._get_segments(samples, 100), [{'start': 38, 'end': 60}])

    def test_temporal_consistency_can_be_disabled(self):
        self.operator.params['use_temporal_consistency'] = 0
        # a static overlay is then kept, as the geometry alone cannot tell it from subtitles
        samples = self._samples(40, set(range(20, 30)), template='STATIC OVERLAY')
        self.assertEqual(self.operator._get_segments(samples, 100), [{'start': 38, 'end': 60}])


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
            f'yadif,fps=1/{INTERVAL},crop=iw:ih*0.25:0:ih*(1-0.25),scale=640:120,format=gray',
        )

    def test_deinterlace_can_be_disabled(self):
        self.operator.params['deinterlace'] = 0
        self.assertNotIn('yadif', self.operator._get_sample_filter())


class ParseOcrTsvTestCase(unittest.TestCase):
    '''_parse_ocr_tsv: the tesseract TSV output to one list of word dicts per sample'''

    HEADER = 'level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext'

    def setUp(self):
        self.operator = DetectSubsTesseract()
        self.operator.params = dict(DEFAULT_PARAMS)

    def _row(self, page_num, text, conf=90, left=10, top=90, width=100, height=40):
        ret = f'5\t{page_num}\t1\t1\t1\t1\t{left}\t{top}\t{width}\t{height}\t{conf}\t{text}'
        return ret

    def test_words_are_grouped_by_sample(self):
        tsv = '\n'.join([
            self.HEADER,
            self._row(1, 'hello'),
            self._row(2, 'world'),
            self._row(2, 'again'),
        ])
        samples = self.operator._parse_ocr_tsv(tsv)
        self.assertEqual([[word['text'] for word in sample] for sample in samples], [['hello'], ['world', 'again']])

    def test_geometry_and_confidence_are_read(self):
        tsv = '\n'.join([self.HEADER, self._row(1, 'hello', conf=72, left=12, top=34, width=56, height=78)])
        self.assertEqual(
            self.operator._parse_ocr_tsv(tsv),
            [[{'text': 'hello', 'conf': 72, 'left': 12, 'top': 34, 'width': 56, 'height': 78}]],
        )

    def test_rows_without_text_are_dropped(self):
        tsv = '\n'.join([self.HEADER, self._row(1, ''), self._row(1, ' ')])
        self.assertEqual(self.operator._parse_ocr_tsv(tsv), [[]])

    def test_confidence_can_be_negative(self):
        tsv = '\n'.join([self.HEADER, self._row(1, 'x', conf=-1)])
        self.assertEqual(self.operator._parse_ocr_tsv(tsv)[0][0]['conf'], -1)

    def test_missing_sample_gives_empty_lists(self):
        # page 3 is the only one with text, the pages before it are still represented
        tsv = '\n'.join([self.HEADER, self._row(3, 'hello')])
        samples = self.operator._parse_ocr_tsv(tsv)
        self.assertEqual([len(sample) for sample in samples], [0, 0, 1])


class GetSampleWordsTestCase(unittest.TestCase):
    '''_get_sample_words: the word boxes of a sample that look like subtitles'''

    def setUp(self):
        self.operator = DetectSubsTesseract()
        self.operator.params = dict(DEFAULT_PARAMS)

    def test_clean_centered_word_is_kept(self):
        clean = centered_word('hello', 0)
        self.assertEqual(self.operator._get_sample_words([clean]), [clean])

    def test_low_confidence_word_is_dropped(self):
        self.assertEqual(self.operator._get_sample_words([word('hello', conf=10)]), [])

    def test_word_above_the_band_is_dropped(self):
        self.assertEqual(self.operator._get_sample_words([word('hello', top=10)]), [])

    def test_word_reaching_the_edge_is_dropped(self):
        self.assertEqual(self.operator._get_sample_words([word('hello', left=0, width=200)]), [])
        self.assertEqual(self.operator._get_sample_words([word('hello', left=600, width=40)]), [])

    def test_too_short_word_box_is_dropped(self):
        self.assertEqual(self.operator._get_sample_words([word('hello', height=5)]), [])

    def test_geometry_filter_can_be_disabled(self):
        self.operator.params['use_word_geometry'] = 0
        edge = word('hello', left=0, width=200, conf=10)
        self.assertEqual(self.operator._get_sample_words([edge]), [edge])


if __name__ == '__main__':
    unittest.main()
