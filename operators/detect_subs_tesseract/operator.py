# Script created by opencode:e-research/arc:apex
# New operator detect_subs_tesseract sampling the bottom band of a clip at regular intervals with ffmpeg,
# OCRing the samples with tesseract and writing the periods with burned-in subtitles into hard_sub_segments.json.

from pathlib import Path
from ..base.operator import Operator
import re

# name of the file where the burned-in subtitle segments are saved in the clip folder
SEGMENTS_FILE_NAME = 'hard_sub_segments.json'
# the samples are temporary files, the folder name must start with _ to be ignored by the other operators
SAMPLES_FOLDER_NAME = '_subs_samples'
SAMPLE_FILE_TEMPLATE = '%05d.png'
SAMPLES_LIST_FILE_NAME = 'samples.txt'
OCR_BASE_NAME = 'ocr'
OCR_TSV_FILE_NAME = 'ocr.tsv'
# folders of the clips subtitled by sub_clips_ffmpeg, ignored by this operator
SUB_SUFFIX = '-sub'
CONTAINER_DATA_PATH = Path('/data')
# a sample is positive when its OCR text contains at least this many characters
MIN_TEXT_CHARS = 2
# width in pixels of the downsampled samples, small enough for OCR to stay fast
SAMPLE_WIDTH = 640
# height in pixels of the downsampled samples, the geometry of the word boxes is read in that pixel space
SAMPLE_HEIGHT = 120
# columns of the tesseract TSV output, in which a row holds one detected word
TSV_HEADER = ['level', 'page_num', 'block_num', 'par_num', 'line_num', 'word_num', 'left', 'top', 'width', 'height', 'conf', 'text']


class DetectSubsTesseract(Operator):
    '''Detect the periods of burned-in subtitles in clips using tesseract OCR'''

    def get_supported_arguments(self):
        ret = super().get_supported_arguments()
        ret['redo'] = True
        ret['filter'] = True
        ret['skip'] = True
        return ret

    def _apply(self):
        ret = None

        stats = {
            'created': 0,
            'existing': 0,
            'skipped': 0,
            'segments': 0,
        }

        for col in self.context['collections']:
            collection_path = col['attributes']['path']
            for video_folder_path in sorted(collection_path.iterdir()):
                if not video_folder_path.is_dir():
                    continue
                for clip_folder_path in sorted(video_folder_path.iterdir()):
                    # do not process the folders of subtitled clips created by sub_clips_ffmpeg
                    if not clip_folder_path.is_dir() or clip_folder_path.name.endswith(SUB_SUFFIX):
                        continue
                    clip_path = self._get_video_file_path(clip_folder_path)
                    if clip_path:
                        outcome, segments_count = self._detect(clip_path, collection_path)
                        if outcome:
                            stats[outcome] += 1
                            stats['segments'] += segments_count

        self._log(f"hard sub segment files created: {stats['created']}; already existing: {stats['existing']}; clips skipped: {stats['skipped']}; burned-in subtitle segments found: {stats['segments']}")

        return ret

    def _detect(self, clip_path: Path, collection_path: Path):
        '''Detects the burned-in subtitle segments of a clip and writes them into a json file.
        Returns an (outcome, segments count) tuple where outcome is the name of the stats counter
        the clip has been processed with, None if not processed'''
        ret = None
        segments_count = 0

        if not self._is_path_selected(clip_path):
            return ret, segments_count

        segments_path = clip_path.parent / SEGMENTS_FILE_NAME

        if not self._is_redo() and segments_path.exists():
            ret = 'existing'
        else:
            # the duration of the clip is read from its name, following the framesense convention
            duration_seconds = self.get_duration_seconds_from_clip_path(clip_path)
            samples_folder_path = clip_path.parent / SAMPLES_FOLDER_NAME

            self._log(segments_path)

            texts = self._ocr_samples(clip_path, samples_folder_path, collection_path)

            if texts is None:
                self._warn(f'Burned-in subtitles not detected in clip: {clip_path}')
                ret = 'skipped'
            else:
                segments = self._get_segments(texts, duration_seconds)
                self.write_json(segments_path, segments)
                segments_count = len(segments)
                ret = 'created'

            self._cleanup_samples(samples_folder_path)

        return ret, segments_count

    def _ocr_samples(self, clip_path: Path, samples_folder_path: Path, collection_path: Path):
        '''Extracts the samples of the bottom band of the clip with ffmpeg, then OCRs them all in a single
        tesseract call. Returns one list of word dicts per sample (empty for the samples without text),
        None if the extraction or the OCR failed'''
        ret = None

        self._remove_samples(samples_folder_path)
        samples_folder_path.mkdir(exist_ok=True)

        command_args = [
            'ffmpeg',
            '-i', clip_path,
            '-vf', self._get_sample_filter(),
            samples_folder_path / SAMPLE_FILE_TEMPLATE,
        ]
        res = self._run_in_operator_container(command_args, [collection_path, CONTAINER_DATA_PATH], same_user=True, skip=self._is_skip())

        if res.returncode > 0:
            return ret

        sample_file_paths = sorted(samples_folder_path.glob('*.png'))
        if not sample_file_paths:
            self._warn(f'No samples extracted from clip: {clip_path}')
            return ret

        # the list file gives tesseract the paths of the samples within the container
        container_sample_paths = [CONTAINER_DATA_PATH / p.relative_to(collection_path) for p in sample_file_paths]
        (samples_folder_path / SAMPLES_LIST_FILE_NAME).write_text('\n'.join(str(p) for p in container_sample_paths))

        command_args = [
            'tesseract',
            samples_folder_path / SAMPLES_LIST_FILE_NAME,
            samples_folder_path / OCR_BASE_NAME,
            '-l', str(self.get_param('ocr_lang')),
            # the tsv output gives the geometry and confidence of every word, on which the
            # subtitle-like filtering relies to tell subtitles apart from scene text
            'tsv',
        ]
        res = self._run_in_operator_container(command_args, [collection_path, CONTAINER_DATA_PATH], same_user=True, skip=self._is_skip())

        if res.returncode == 0:
            ocr_path = samples_folder_path / OCR_TSV_FILE_NAME
            if ocr_path.exists():
                ret = self._parse_ocr_tsv(ocr_path.read_text())

        return ret

    def _parse_ocr_tsv(self, tsv_text: str) -> list:
        '''Parses the tesseract TSV output into one list of word dicts per sample,
        a word dict holding its left, top, width, height, confidence and text.
        The samples are ordered as in the input list file (the page_num of a row gives its sample)'''
        ret = []

        lines = tsv_text.splitlines()
        if not lines or lines[0].split('\t') != TSV_HEADER:
            self._warn(f'Unexpected tesseract TSV header, columns may have shifted: {lines[0] if lines else ""}')

        # page_num is 1-based in the TSV, the samples are given to tesseract in order
        for line in lines[1:]:
            fields = line.split('\t')
            if len(fields) != len(TSV_HEADER):
                continue
            row = dict(zip(TSV_HEADER, fields))
            page_num = int(row['page_num'])
            # a sample with no text still gets an entry, so the sample indices stay aligned
            while len(ret) < page_num:
                ret.append([])
            if not row['text'].strip():
                continue
            ret[page_num - 1].append({
                'left': int(row['left']),
                'top': int(row['top']),
                'width': int(row['width']),
                'height': int(row['height']),
                'conf': int(float(row['conf'])),
                'text': row['text'],
            })

        return ret

    def _get_sample_filter(self) -> str:
        '''Returns the FFMPEG video filter downsampling a clip into small grayscale samples of its bottom band'''
        ret = None

        interval_seconds = self.get_param('sample_interval_secs')
        band_height = self.get_param('band_height')

        filters = []
        # broadcast video is usually interlaced, deinterlacing improves the OCR of the subtitles;
        # int() keeps the check robust to string values ("0"/"1") coming from environment variables
        if int(self.get_param('deinterlace', 1)):
            filters.append('yadif')
        filters.append(f'fps=1/{interval_seconds}')
        filters.append(f'crop=iw:ih*{band_height}:0:ih*(1-{band_height})')
        filters.append(f'scale={SAMPLE_WIDTH}:{SAMPLE_HEIGHT}')
        filters.append('format=gray')

        ret = ','.join(filters)

        return ret

    def _get_segments(self, samples: list, duration_seconds: float) -> list:
        '''Returns the burned-in subtitle segments as a list of {start, end} timecodes in seconds,
        from the word boxes OCR-ed in each sample of the clip, the sample i being taken at i * sample_interval_secs'''
        ret = []

        interval_seconds = self.get_param('sample_interval_secs')

        positive_samples = []
        for i, words in enumerate(samples):
            sample_words = self._get_sample_words(words)
            text = self._normalize_text(' '.join(word['text'] for word in sample_words))
            if len(text) >= MIN_TEXT_CHARS:
                positive_samples.append((i * interval_seconds, text, self._get_median_top(sample_words)))

        runs = self._get_runs(positive_samples)

        for run in runs:
            segment = self._get_run_segment(run, duration_seconds)
            if segment and self._is_consistent(run):
                ret.append(segment)

        return ret

    def _get_sample_words(self, words: list) -> list:
        '''Returns the word boxes of a sample that look like subtitles: confident enough, clear of the
        frame edges, within the subtitle band and with a glyph height in the expected range.
        All the filters are skipped when use_word_geometry is disabled.
        The geometry is expressed in the pixel space of the sample image'''
        ret = []

        if not int(self.get_param('use_word_geometry', 1)):
            ret = words
            return ret

        # the sample is scaled to SAMPLE_WIDTH wide and SAMPLE_HEIGHT tall
        band_top = self.get_param('subtitle_band_top')
        band_bottom = self.get_param('subtitle_band_bottom')
        edge_margin = self.get_param('edge_margin')
        min_height = self.get_param('min_word_height')
        max_height = self.get_param('max_word_height')
        min_conf = self.get_param('min_word_conf')

        for word in words:
            if word['conf'] < min_conf:
                continue
            # the word box must stay clear of both frame edges, where scene signage tends to sit
            if word['left'] < SAMPLE_WIDTH * edge_margin:
                continue
            if word['left'] + word['width'] > SAMPLE_WIDTH * (1 - edge_margin):
                continue
            if word['top'] < SAMPLE_HEIGHT * band_top or word['top'] + word['height'] > SAMPLE_HEIGHT * band_bottom:
                continue
            if word['height'] < SAMPLE_HEIGHT * min_height or word['height'] > SAMPLE_HEIGHT * max_height:
                continue
            ret.append(word)

        return ret

    def _get_median_top(self, words: list) -> float:
        '''Returns the median top coordinate of the word boxes of a sample, 0 if there is none'''
        ret = 0

        if words:
            tops = sorted(word['top'] for word in words)
            middle = len(tops) // 2
            ret = tops[middle] if len(tops) % 2 else (tops[middle - 1] + tops[middle]) / 2

        return ret

    def _get_runs(self, positive_samples: list) -> list:
        '''Returns the positive samples grouped into runs, a gap between two consecutive samples
        longer than gap_tolerance_secs starting a new run'''
        ret = []
        gap_tolerance_seconds = self.get_param('gap_tolerance_secs')
        current_run = []
        previous_time = None

        for time, text, top in positive_samples:
            if current_run and time - previous_time > gap_tolerance_seconds:
                ret.append(current_run)
                current_run = []
            current_run.append((time, text, top))
            previous_time = time

        if current_run:
            ret.append(current_run)

        return ret

    def _get_run_segment(self, run: list, duration_seconds: float):
        '''Returns the burned-in subtitle segment covered by a run of positive samples as a {start, end}
        dict, its boundaries padded by one sample interval so that the subtitles appearing between two
        samples are covered, None if the padded segment is shorter than min_segment_secs'''
        ret = None

        interval_seconds = self.get_param('sample_interval_secs')
        start = max(0, run[0][0] - interval_seconds)
        end = min(duration_seconds, run[-1][0] + interval_seconds)

        if end - start >= self.get_param('min_segment_secs'):
            ret = {
                'start': round(start, 3),
                'end': round(end, 3),
            }

        return ret

    def _is_consistent(self, run: list) -> bool:
        '''Returns True if a run of positive samples behaves like subtitles:
        its texts change from cue to cue (at least min_distinct_texts distinct texts)
        and its words sit on a stable baseline (the median top drifts by at most max_baseline_drift
        of the sample height).
        A static overlay repeating the same text, or scene text wandering with the camera, fails one of the two.
        The check is skipped when use_temporal_consistency is disabled'''
        ret = True

        if not int(self.get_param('use_temporal_consistency', 1)):
            return ret

        if len({text for time, text, top in run}) < self.get_param('min_distinct_texts'):
            ret = False
        else:
            tops = [top for time, text, top in run]
            drift = (max(tops) - min(tops)) / SAMPLE_HEIGHT
            if drift > self.get_param('max_baseline_drift'):
                ret = False

        return ret

    def _normalize_text(self, text: str) -> str:
        '''Returns an OCR text lowered and stripped of the characters that are not alphanumeric'''
        ret = re.sub(r'[^a-z0-9 ]', '', text.lower()).strip()
        return ret

    def _cleanup_samples(self, samples_folder_path: Path):
        '''Removes the samples folder when caching is disabled, so that nothing persists on disk.
        No-op if the folder does not exist'''
        ret = None

        # int() keeps the check robust to string values ("0"/"1") coming from environment variables,
        # whereas bool("0") would wrongly evaluate to True
        if not int(self.get_param('cache_samples', 0)):
            self._remove_samples(samples_folder_path)

        return ret

    def _remove_samples(self, samples_folder_path: Path):
        '''Deletes the content of the samples folder, then the folder itself.
        No-op if the folder does not exist'''
        ret = None

        if samples_folder_path.exists():
            for file_path in sorted(samples_folder_path.iterdir()):
                file_path.unlink()
            if not any(samples_folder_path.iterdir()):
                samples_folder_path.rmdir()

        return ret
