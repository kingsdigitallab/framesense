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
OCR_FILE_NAME = 'ocr.txt'
# folders of the clips subtitled by sub_clips_ffmpeg, ignored by this operator
SUB_SUFFIX = '-sub'
CONTAINER_DATA_PATH = Path('/data')
# a sample is positive when its OCR text contains at least this many characters
MIN_TEXT_CHARS = 2
# width in pixels of the downsampled samples, small enough for OCR to stay fast
SAMPLE_WIDTH = 640
# tesseract separates the texts of the images of a list file with this character
FORM_FEED = '\f'


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
        tesseract call. Returns the list of the OCR text of the samples (empty strings for the samples
        without text), None if the extraction or the OCR failed'''
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
        ]
        res = self._run_in_operator_container(command_args, [collection_path, CONTAINER_DATA_PATH], same_user=True, skip=self._is_skip())

        if res.returncode == 0:
            ocr_path = samples_folder_path / OCR_FILE_NAME
            if ocr_path.exists():
                # tesseract writes the text of each sample, separated by form feeds
                ret = ocr_path.read_text().split(FORM_FEED)

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
        filters.append(f'scale={SAMPLE_WIDTH}:-2')
        filters.append('format=gray')

        ret = ','.join(filters)

        return ret

    def _get_segments(self, texts: list, duration_seconds: float) -> list:
        '''Returns the burned-in subtitle segments as a list of {start, end} timecodes in seconds,
        from the OCR text of each sample of the clip, the sample i being taken at i * sample_interval_secs'''
        ret = []

        interval_seconds = self.get_param('sample_interval_secs')

        positive_samples = []
        for i, text in enumerate(texts):
            normalized = self._normalize_text(text)
            if len(normalized) >= MIN_TEXT_CHARS:
                positive_samples.append((i * interval_seconds, normalized))

        runs = self._get_runs(positive_samples)

        for run in runs:
            segment = self._get_run_segment(run, duration_seconds)
            if segment and not self._is_static(run):
                ret.append(segment)

        return ret

    def _get_runs(self, positive_samples: list) -> list:
        '''Returns the positive samples grouped into runs, a gap between two consecutive samples
        longer than gap_tolerance_secs starting a new run'''
        ret = []
        gap_tolerance_seconds = self.get_param('gap_tolerance_secs')
        current_run = []
        previous_time = None

        for time, text in positive_samples:
            if current_run and time - previous_time > gap_tolerance_seconds:
                ret.append(current_run)
                current_run = []
            current_run.append((time, text))
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

    def _is_static(self, run: list) -> bool:
        '''Returns True if a run of positive samples holds fewer than min_distinct_texts distinct texts,
        in which case it is more likely a static overlay (logo, ticker, name strap) than subtitles'''
        ret = len({text for time, text in run}) < self.get_param('min_distinct_texts')
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
