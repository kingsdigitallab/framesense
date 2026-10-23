# Script created by opencode:opencode/big-pickle
# New operator separate_clips_ffmpeg splitting the clips of a video around the programme separators (sep1 answer in clip_answers.json) into new -prog clips.

import re
from pathlib import Path

from ..base.operator import Operator
import itertools

PROG_SUFFIX = '-prog'
TMP_SUFFIX = '-tmp'
CHUNKS_FOLDER_NAME = 'chunks'
ANSWERS_FILE_NAME = 'clip_answers.json'
QUESTION_KEY = 'sep1'
DEFAULT_MIN_SEGMENT_SECONDS = 1
DEFAULT_SEP_PROD_ABSORB_SECONDS = 2
CONTAINER_DATA_PATH = Path('/data')
DEFAULT_CUT_MODE = 'smart'
# the smart cut re-encodes the whole segment with a near-lossless quality, in a single
# ffmpeg command, so that the output is second-accurate and always playable
DEFAULT_SMART_CRF = 18
DEFAULT_SMART_PRESET = 'veryfast'
SMART_CUT_VIDEO_CODEC = 'libx264'


class SeparateClipsFFMPEG(Operator):
    '''Split clips around the programme separators of the sep1 answer 
    in clip_answers.json into new -prog clips'''

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
            collection_path: Path = col['attributes']['path']
            for video_folder_path in sorted(collection_path.iterdir()):
                if not video_folder_path.is_dir():
                    continue

                for clip_folder_path in sorted(video_folder_path.iterdir()):
                    # only the -prog clip folders created by this operator are skipped
                    if not clip_folder_path.is_dir() or clip_folder_path.name.endswith(PROG_SUFFIX) or clip_folder_path.name == CHUNKS_FOLDER_NAME:
                        continue

                    clip_path = self._get_video_file_path(clip_folder_path, direct_child_only=True)
                    if not clip_path:
                        continue

                    outcomes = self._split_clip(clip_path, collection_path)
                    for outcome, count in outcomes.items():
                        stats[outcome] += count

        self._log(f"prog clips created: {stats['created']}; already existing: {stats['existing']}; clips skipped: {stats['skipped']}; whole clips symlinked: {stats['linked']}; clips without separators answer: {stats['missing']}")

        return ret

    def _get_nearest_separators(self, clip_folder_path: Path):
        '''search for separators in ANSWERS_FILE_NAME
        starting from the given clip_folder_path 
        then iteratively trying sibling folders 
        by removing on tag from the suffic each time.
        '''
        ret = None
        path = clip_folder_path
        while path.is_dir():
            ret = self._get_separators(path)
            if ret: break
            path = path.with_name('-'.join(path.name.split('-')[:-1]))
        return ret

    def _get_separators(self, clip_folder_path: Path):
        '''Returns the programme separators of the sep1 answer 
        as a list of (start, end, prod) tuples, 
        with the timecodes in seconds relative to the clip and prod the production information, 
        None if there is no sep1 answer for the clip'''
        ret = None

        answers_path = clip_folder_path / ANSWERS_FILE_NAME
        if answers_path.is_file():
            answers = self._read_data_file(answers_path, is_data_dict=True)
            sep1 = answers['data'].get(QUESTION_KEY, None)
            if sep1 is not None:
                answer = sep1.get('answer', []) if isinstance(sep1, dict) else sep1
                ret = []
                if not isinstance(answer, list):
                    self._warn(f'Invalid {QUESTION_KEY} answer in {ANSWERS_FILE_NAME} of clip {clip_folder_path.name}, clip skipped')
                    ret = None
                else:
                    for entry in answer:
                        separator = self._get_separator(entry)
                        if separator:
                            ret.append(separator)
                    self._log(f'{clip_folder_path.name}: {len(ret)} programme separators')

        return ret

    def _get_separator(self, entry):
        '''Returns the separator of an answer entry 
        as a (start, end, prod) tuple, 
        with the timecodes in seconds and prod the production information ('' if none), 
        None if invalid'''
        ret = None

        if not isinstance(entry, dict):
            self._warn(f'Separator entry is not an object, ignored: {entry}')
        else:
            start = self.get_seconds_from_timecode(entry.get('start', None))
            end = self.get_seconds_from_timecode(entry.get('end', None))
            prod = str(entry.get('prod') or '').strip()

            if start is None or end is None:
                self._warn(f'Separator entry with missing or invalid timecodes, ignored: {entry}')
            elif end < start:
                self._warn(f'Separator entry ending before it starts, ignored: {entry}')
            else:
                ret = (start, end, prod)

        return ret

    def _split_clip(self, clip_path: Path, collection_path: Path) -> dict:
        '''Splits a clip around the programme separators into -prog clips 
        placed in sibling folders next to the original one.
        Returns a dict of stats counters and their number of occurrences'''
        ret = {}

        if not self._is_path_selected(clip_path):
            return ret

        clip_duration_secs = self.get_duration_seconds_from_clip_path(clip_path)
        if clip_duration_secs is None:
            self._warn(f'Could not read the duration of the clip, not split: {clip_path}')
            ret['skipped'] = 1
            return ret
        
        clip_folder_path = clip_path.parent
        separators = self._get_nearest_separators(clip_folder_path)
        if separators is None:
            self._warn(f'No {QUESTION_KEY} answer in {ANSWERS_FILE_NAME} of clip {clip_folder_path.name}, clip skipped')
            ret['missing'] = 1
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
        '''Returns the (start, end) segments of the clip 
        free of programme separators, 
        the separators timecodes being relative to the clip.
        The start of a segment is moved back into the preceding separator when it carries
        production information, up to sep_prod_absorb_seconds, so that the production card
        visible at the end of the separator is included in the programme clip;
        it never starts before the previous separator.'''
        ret = []

        absorb_secs = int(self.get_param('sep_prod_absorb_seconds', DEFAULT_SEP_PROD_ABSORB_SECONDS))

        boundaries = []
        for start_secs, end_secs, prod in sorted(separators, key=lambda s: s[0]):
            clipped_start = max(start_secs, 0)
            clipped_end = min(end_secs, clip_duration_secs)
            if clipped_start < clipped_end:
                boundaries.append((clipped_start, clipped_end, prod))

        if boundaries:
            # the end of the clip acts as a final separator, so the trailing programme
            # is built by the same loop and absorbs the production card like the inner ones
            boundaries.append((clip_duration_secs, clip_duration_secs, ''))

            if boundaries[0][0] > 0:
                ret.append((0, boundaries[0][0]))

            for i, current in enumerate(boundaries[1:]):
                previous = boundaries[i]
                if previous[1] < current[0]:
                    start_secs = previous[1]
                    if previous[2] and absorb_secs > 0:
                        # move the start back into the tail of the preceding separator
                        # to include its production card, without reaching the separator
                        # before it (or before the beginning of the clip)
                        floor_secs = boundaries[i - 1][1] if i > 0 else 0
                        start_secs = max(floor_secs, previous[0], previous[1] - absorb_secs)
                    ret.append((start_secs, current[0]))

        return ret

    def _make_prog_clip(self, clip_path: Path, start_secs: int, end_secs: int, collection_path: Path):
        '''Cuts the segment of the clip between two programme separators 
        into a new -prog clip, placed in its own folder next to the original one.
        Returns the name of the stats counter the clip has been processed with, 
        None if not processed'''
        ret = None

        duration_secs = end_secs - start_secs
        name = f'{self.get_hhmmss(start_secs).replace(":", ".")}-{duration_secs}{self.get_clip_suffix(clip_path)}{PROG_SUFFIX}'
        prog_folder_path = clip_path.parent.parent / name
        prog_clip_path = prog_folder_path / f'{name}{clip_path.suffix}'

        if self._is_redo() or not prog_clip_path.exists():
            prog_folder_path.mkdir(exist_ok=True)

            # written to a temporary file in the same folder, renamed on completion, so that the operation is atomic
            prog_clip_tmp_path = prog_folder_path / f'{name}{TMP_SUFFIX}{clip_path.suffix}'

            self._log(prog_clip_path)

            cut_mode = self.get_param('cut_mode', DEFAULT_CUT_MODE)
            succeeded = self._cut_clip(clip_path, start_secs, end_secs, prog_clip_tmp_path, collection_path, cut_mode)

            if succeeded:
                prog_clip_tmp_path.rename(prog_clip_path)
                ret = 'created'
            else:
                prog_clip_tmp_path.unlink(missing_ok=True)
                self._warn(f'Clip not split: {clip_path}')
                ret = 'skipped'
        else:
            ret = 'existing'

        return ret

    def _cut_clip(self, clip_path: Path, start_secs: int, end_secs: int, output_path: Path, collection_path: Path, cut_mode: str):
        '''Cuts the segment of a clip into the output file with the requested cut mode, 
        falling back to re-encoding all of it if the smart mode fails.
        Returns True if the output file was produced'''
        ret = False

        if cut_mode == 'smart':
            ret = self._cut_clip_smart(clip_path, start_secs, end_secs, output_path, collection_path)
            if not ret:
                self._warn(f'Smart cut failed, falling back to re-encoding the clip: {clip_path}')
                ret = self._cut_clip_reencode(clip_path, start_secs, end_secs, output_path, collection_path)
        else:
            ret = self._cut_clip_reencode(clip_path, start_secs, end_secs, output_path, collection_path)

        return ret

    def _cut_clip_reencode(self, clip_path: Path, start_secs: int, end_secs: int, output_path: Path, collection_path: Path):
        '''Cuts the segment of a clip into the output file by re-encoding it entirely, second-accurate but lossy.
        Returns True if the output file was produced'''
        ret = False

        command_args = [
            'ffmpeg',
            '-y',
            '-ss', str(start_secs),
            '-i', clip_path,
            '-t', str(end_secs - start_secs),
            output_path,
        ]
        res = self._run_in_operator_container(command_args, (collection_path, CONTAINER_DATA_PATH), same_user=True, skip=self._is_skip())

        ret = res.returncode == 0 and output_path.exists()

        return ret

    def _cut_clip_smart(self, clip_path: Path, start_secs: int, end_secs: int, output_path: Path, collection_path: Path):
        '''Cuts the segment of a clip into the output file 
        by re-encoding its whole video stream with a near-lossless quality 
        and copying its audio stream.
        A single ffmpeg command is used so that the output is one uniform stream: second-accurate and always playable.
        Returns True if the output file was produced'''
        ret = False

        smart_crf = int(self.get_param('smart_crf', DEFAULT_SMART_CRF))

        command_args = [
            'ffmpeg',
            '-y',
            '-ss', str(start_secs),
            '-i', clip_path,
            '-t', str(end_secs - start_secs),
            '-c:v', SMART_CUT_VIDEO_CODEC,
            '-crf', str(smart_crf),
            '-preset', str(self.get_param('smart_preset', DEFAULT_SMART_PRESET)),
            '-c:a', 'copy',
            output_path,
        ]
        # the container call itself cannot fail the operator run: when the smart cut fails, we fall back to re-encoding
        res = self._run_in_operator_container(command_args, (collection_path, CONTAINER_DATA_PATH), same_user=True, skip=True)

        ret = res.returncode == 0 and output_path.exists()

        return ret

    def _link_whole_clip(self, clip_path: Path):
        '''For a clip without any programme separator in it, 
        symlinks the clip to a new -prog clip in its own folder next to the original one.
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

