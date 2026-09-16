# Script created by opencode:opencode/big-pickle
# New operator separate_clips_ffmpeg splitting the clips of a video around the programme separators (sep1 answer in video_answers.json) into new -prog clips.

from pathlib import Path
from ..base.operator import Operator
import re
import json

PROG_SUFFIX = '-prog'
TMP_SUFFIX = '-tmp'
CHUNKS_FOLDER_NAME = 'chunks'
ANSWERS_FILE_NAME = 'video_answers.json'
QUESTION_KEY = 'sep1'
DEFAULT_MIN_SEGMENT_SECONDS = 1
CONTAINER_DATA_PATH = Path('/data')


class SeparateClipsFFMPEG(Operator):
    '''Split clips around the programme separators of the sep1 answer in video_answers.json into new -prog clips'''

    def get_supported_arguments(self):
        ret = super().get_supported_arguments()
        ret['filter'] = True
        ret['redo'] = True
        ret['skip'] = True
        return ret

    def _apply(self):
        ret = None

        stats = {
            'created': 0,
            'existing': 0,
            'skipped': 0,
            'missing': 0,
            'linked': 0,
        }

        for col in self.context['collections']:
            collection_path = col['attributes']['path']
            for video_folder_path in sorted(collection_path.iterdir()):
                if not video_folder_path.is_dir():
                    continue

                separators = self._get_separators(video_folder_path)
                if separators is None:
                    stats['missing'] += 1
                    self._warn(f'No {QUESTION_KEY} answer in {ANSWERS_FILE_NAME} of video {video_folder_path.name}, video skipped')
                    continue

                for clip_folder_path in sorted(video_folder_path.iterdir()):
                    # only the -prog clip folders created by this operator are skipped
                    if not clip_folder_path.is_dir() or clip_folder_path.name.endswith(PROG_SUFFIX) or clip_folder_path.name == CHUNKS_FOLDER_NAME:
                        continue

                    clip_path = self._get_video_file_path(clip_folder_path, direct_child_only=True)
                    if not clip_path:
                        continue

                    outcomes = self._split_clip(clip_path, separators, collection_path)
                    for outcome, count in outcomes.items():
                        stats[outcome] += count

        self._log(f"prog clips created: {stats['created']}; already existing: {stats['existing']}; clips skipped: {stats['skipped']}; whole clips symlinked: {stats['linked']}; videos without separators answer: {stats['missing']}")

        return ret

    def _get_separators(self, video_folder_path: Path):
        '''Returns the programme separators of the sep1 answer as a list of (start, end) seconds relative to the clips, None if there is no sep1 answer for the video'''
        ret = None

        answers_path = video_folder_path / ANSWERS_FILE_NAME
        if answers_path.is_file():
            answers = self._read_data_file(answers_path, is_data_dict=True)
            sep1 = answers['data'].get(QUESTION_KEY, None)
            if sep1 is not None:
                answer = sep1.get('answer', []) if isinstance(sep1, dict) else sep1
                ret = []
                if not isinstance(answer, list):
                    self._warn(f'Invalid {QUESTION_KEY} answer in {ANSWERS_FILE_NAME} of video {video_folder_path.name}, video skipped')
                    ret = None
                else:
                    for entry in answer:
                        separator = self._get_separator(entry)
                        if separator:
                            ret.append(separator)
                    self._log(f'{video_folder_path.name}: {len(ret)} programme separators')

        return ret

    def _get_separator(self, entry):
        '''Returns the separator of an answer entry as a (start, end) couple of seconds, None if invalid'''
        ret = None

        if not isinstance(entry, dict):
            self._warn(f'Separator entry is not an object, ignored: {entry}')
        else:
            start = self._get_seconds_from_timecode(entry.get('start', None))
            end = self._get_seconds_from_timecode(entry.get('end', None))

            if start is None or end is None:
                self._warn(f'Separator entry with missing or invalid timecodes, ignored: {entry}')
            elif end < start:
                self._warn(f'Separator entry ending before it starts, ignored: {entry}')
            else:
                ret = (start, end)

        return ret

    def _split_clip(self, clip_path: Path, separators: list, collection_path: Path) -> dict:
        '''Splits a clip around the programme separators into -prog clips placed in sibling folders next to the original one.
        Returns a dict of stats counters and their number of occurrences'''
        ret = {}

        if not self._is_path_selected(clip_path):
            return ret

        clip_duration_secs = self._get_clip_duration_seconds(clip_path)
        if clip_duration_secs is None:
            self._warn(f'Could not read the duration of the clip, not split: {clip_path}')
            ret['skipped'] = 1
            return ret

        inside_separators = [
            separator
            for separator in separators
            if separator[0] < clip_duration_secs and separator[1] > 0
        ]

        if not inside_separators:
            outcome = self._link_whole_clip(clip_path)
            if outcome:
                ret[outcome] = 1
        else:
            min_segment_secs = int(self.get_param('min_segment_seconds', DEFAULT_MIN_SEGMENT_SECONDS))

            for start_secs, end_secs in self._compute_segments(clip_duration_secs, inside_separators):
                if (end_secs - start_secs) < min_segment_secs:
                    continue

                outcome = self._make_prog_clip(clip_path, start_secs, end_secs, collection_path)
                if outcome:
                    ret[outcome] = ret.get(outcome, 0) + 1

        return ret

    def _compute_segments(self, clip_duration_secs: int, separators: list) -> list:
        '''Returns the (start, end) segments of the clip free of programme separators, the separators timecodes being relative to the clip'''
        ret = []

        boundaries = []
        for start_secs, end_secs in sorted(separators, key=lambda s: s[0]):
            clipped_start = max(start_secs, 0)
            clipped_end = min(end_secs, clip_duration_secs)
            if clipped_start < clipped_end:
                boundaries.append((clipped_start, clipped_end))

        if boundaries:
            if boundaries[0][0] > 0:
                ret.append((0, boundaries[0][0]))

            for previous, current in zip(boundaries, boundaries[1:]):
                if previous[1] < current[0]:
                    ret.append((previous[1], current[0]))

            if boundaries[-1][1] < clip_duration_secs:
                ret.append((boundaries[-1][1], clip_duration_secs))

        return ret

    def _make_prog_clip(self, clip_path: Path, start_secs: int, end_secs: int, collection_path: Path):
        '''Cuts the segment of the clip between two programme separators into a new -prog clip, placed in its own folder next to the original one.
        Returns the name of the stats counter the clip has been processed with, None if not processed'''
        ret = None

        duration_secs = end_secs - start_secs
        name = f'{self._get_hhmmss(start_secs).replace(":", ".")}-{duration_secs}{self._get_clip_suffix(clip_path)}{PROG_SUFFIX}'
        prog_folder_path = clip_path.parent.parent / name
        prog_clip_path = prog_folder_path / f'{name}{clip_path.suffix}'

        if self._is_redo() or not prog_clip_path.exists():
            prog_folder_path.mkdir(exist_ok=True)

            # written to a temporary file in the same folder, renamed on completion, so that the operation is atomic
            prog_clip_tmp_path = prog_folder_path / f'{name}{TMP_SUFFIX}{clip_path.suffix}'

            self._log(prog_clip_path)

            command = [
                'ffmpeg',
                '-y',
                '-ss', str(start_secs),
                '-i', clip_path,
                '-t', str(duration_secs),
                prog_clip_tmp_path,
            ]
            res = self._run_in_operator_container(command, [collection_path, CONTAINER_DATA_PATH], same_user=True, skip=self._is_skip())

            if res.returncode > 0:
                prog_clip_tmp_path.unlink(missing_ok=True)
                self._warn(f'Clip not split: {clip_path}')
                ret = 'skipped'
            else:
                prog_clip_tmp_path.rename(prog_clip_path)
                ret = 'created'
        else:
            ret = 'existing'

        return ret

    def _link_whole_clip(self, clip_path: Path):
        '''For a clip without any programme separator in it, symlinks the clip to a new -prog clip in its own folder next to the original one.
        Returns the name of the stats counter the clip has been processed with'''
        ret = 'linked'

        name = f'{clip_path.parent.name}{PROG_SUFFIX}'
        prog_folder_path = clip_path.parent.parent / name
        prog_clip_path = prog_folder_path / f'{name}{clip_path.suffix}'

        if not self._is_redo() and prog_clip_path.exists():
            ret = 'existing'
        else:
            prog_folder_path.mkdir(exist_ok=True)

            if self._is_redo():
                prog_clip_path.unlink(missing_ok=True)

            self._log(prog_clip_path)

            # relative symlink to the input clip, e.g. ../<clip>/<clip>.mp4
            prog_clip_path.symlink_to(Path('..') / clip_path.parent.name / clip_path.name)

        return ret

    def _get_clip_suffix(self, clip_path: Path) -> str:
        '''Returns the suffix of the clip folder name after its timecodes, '' if there is none, e.g. -full for 00.00.00-6582-full'''
        ret = ''

        match = re.match(r'^\d{2}\.\d{2}\.\d{2}-\d+(?P<suffix>-[^0-9].*)?$', clip_path.parent.name)
        if match and match.group('suffix'):
            ret = match.group('suffix')

        return ret

    def _get_clip_duration_seconds(self, clip_path: Path):
        '''Returns the duration of the clip in seconds, None if it could not be read'''
        ret = None

        binding = [clip_path.parent, Path('/data')]
        command_args = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'json',
            clip_path,
        ]
        res = self._run_in_operator_container(command_args, binding, skip=self._is_skip())

        if res.returncode == 0:
            try:
                metadata = json.loads(res.stdout)
                ret = int(float(metadata['format']['duration']))
            except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                pass

        return ret

    def _get_seconds_from_timecode(self, timecode):
        '''Converts a timecode into seconds; accepts HH:MM:SS, MM:SS or plain seconds; None if invalid'''
        ret = None

        if isinstance(timecode, (int, float)):
            ret = int(timecode)
        else:
            match = re.match(r'^\s*(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:[.,]\d+)?\s*$', str(timecode))
            if match:
                ret = int(match.group(1) or 0) * 3600 + int(match.group(2)) * 60 + int(match.group(3))

        return ret

    def _get_hhmmss(self, seconds):
        '''Formats a duration in seconds as HH:MM:SS'''
        hours = int(seconds // 3600)
        seconds %= 3600
        minutes = int(seconds // 60)
        seconds %= 60
        ret = f'{hours:02d}:{minutes:02d}:{int(seconds):02d}'
        return ret