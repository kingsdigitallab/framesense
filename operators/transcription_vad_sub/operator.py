# Script created by opencode:e-research/arc:apex
# Prompt: create a new operator transcription_vad_sub which takes a clip X/transcription.json,
# keeps only the segments overlapping a voice segment of X/voice_segments.json
# (or all the segments if that file is absent) and writes X/X.srt.

import re
from pathlib import Path
from ..base.operator import Operator

TRANSCRIPTION_FILE_NAME = 'transcription.json'
VOICE_SEGMENTS_FILE_NAME = 'voice_segments.json'
# folders of the clips subtitled by sub_clips_ffmpeg, ignored by this operator
SUB_SUFFIX = '-sub'
# minimum overlap (seconds) between a transcription item and a voice segment to keep it
MIN_OVERLAP_SECONDS = 0.25
# runs of at least this many consecutive identical cues are collapsed to a single cue
MAX_REPEAT_RUN = 3
# pieces longer than this many characters are split into multiple pieces
MAX_CUE_CHARS = 42
# pieces shorter than this many words are merged into an adjacent piece
MIN_CUE_WORDS = 4


class TranscriptionVADSub(Operator):
    '''Write the transcriptions of clips into srt subtitle files, keeping only the segments overlapping a voice segment'''

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
            'stale': 0,
            'skipped': 0,
            'missing': 0,
            'unfiltered': 0,
            'short_overlap_dropped': 0,
            'repeated_dropped': 0,
            'split': 0,
        }

        for col in self.context['collections']:
            for video_folder_path in sorted(col['attributes']['path'].iterdir()):
                if video_folder_path.is_dir():
                    for clip_folder_path in sorted(video_folder_path.iterdir()):
                        # do not process the folders of subtitled clips created by sub_clips_ffmpeg
                        if clip_folder_path.is_dir() and not clip_folder_path.name.endswith(SUB_SUFFIX):
                            clip_path = self._get_video_file_path(clip_folder_path)
                            if clip_path:
                                outcome, dropped_counts = self._write_srt(clip_path)
                                if outcome:
                                    stats[outcome] += 1
                                    for stat_name, stat_count in dropped_counts.items():
                                        stats[stat_name] += stat_count

        self._log(f"srt files created: {stats['created']}; stale recreated: {stats['stale']}; already existing: {stats['existing']}; clips skipped: {stats['skipped']}; transcriptions not found: {stats['missing']}; without voice segments: {stats['unfiltered']}; short-overlap cues dropped: {stats['short_overlap_dropped']}; repeated cues collapsed: {stats['repeated_dropped']}; segments split: {stats['split']}")

        return ret

    def _write_srt(self, clip_path: Path):
        '''Writes the voice-filtered transcription of a clip into a srt file.
        Returns a (outcome, dropped_counts) tuple where outcome is the name of the stats counter
        the clip has been processed with (None if not processed)'''
        ret = None
        dropped_counts = {}

        if not self._is_path_selected(clip_path):
            return ret, dropped_counts

        transcription_path = clip_path.parent / TRANSCRIPTION_FILE_NAME
        voice_segments_path = clip_path.parent / VOICE_SEGMENTS_FILE_NAME

        if not transcription_path.exists():
            self._warn(f'Input transcription not found: {transcription_path}')
            ret = 'missing'
        else:
            srt_path = clip_path.with_suffix('.srt')
            is_stale = srt_path.exists() and self._is_stale(srt_path, transcription_path, voice_segments_path)

            if self._is_redo() or not srt_path.exists() or is_stale:
                is_unfiltered = False
                try:
                    transcription = self.read_json(transcription_path)
                    transcription, split_count = self._split_cues(transcription)
                    if split_count:
                        dropped_counts['split'] = split_count

                    if voice_segments_path.exists():
                        voice_segments = self.read_json(voice_segments_path)
                        overlapping = [item for item in transcription if self._get_max_overlap(item, voice_segments) > 0]
                        cues = [item for item in overlapping if self._is_speech(item, voice_segments)]
                        dropped_counts['short_overlap_dropped'] = len(overlapping) - len(cues)
                        cues = self._merge_tiny_cues(cues)
                        collapsed_cues = self._collapse_repeats(cues)
                        dropped_counts['repeated_dropped'] = len(cues) - len(collapsed_cues)
                        cues = collapsed_cues
                    else:
                        # detect_speech_vad has not been run on the clip: all the segments are kept
                        is_unfiltered = True
                        cues = self._merge_tiny_cues(transcription)

                    self._generate_srt(cues, srt_path)
                except Exception as e:
                    srt_path.unlink(missing_ok=True)
                    error_message = f'Srt not created for clip: {clip_path} ({e})'
                    if self._is_skip():
                        self._warn(error_message)
                        ret = 'skipped'
                    else:
                        self._error(error_message)
                else:
                    if is_unfiltered:
                        ret = 'unfiltered'
                    elif is_stale:
                        ret = 'stale'
                    else:
                        ret = 'created'
            else:
                ret = 'existing'

        return ret, dropped_counts

    def _is_stale(self, srt_path: Path, transcription_path: Path, voice_segments_path: Path):
        '''Returns True if the srt file is older than at least one of its input files'''
        ret = False
        if srt_path.stat().st_mtime < transcription_path.stat().st_mtime:
            ret = True
        elif voice_segments_path.exists() and srt_path.stat().st_mtime < voice_segments_path.stat().st_mtime:
            ret = True
        return ret

    def _get_max_overlap(self, item: dict, voice_segments: list):
        '''Returns the longest overlap in seconds of a transcription item with a voice segment, 0 if no overlap'''
        ret = 0
        for voice_segment in voice_segments:
            overlap = min(item['end'], voice_segment['end']) - max(item['start'], voice_segment['start'])
            if overlap > ret:
                ret = overlap
        return ret

    def _is_speech(self, item: dict, voice_segments: list):
        '''Returns True if the transcription item overlaps a voice segment by at least min_overlap_seconds'''
        min_overlap_seconds = self.get_param('min_overlap_seconds', MIN_OVERLAP_SECONDS)
        ret = self._get_max_overlap(item, voice_segments) >= min_overlap_seconds
        return ret

    def _collapse_repeats(self, cues: list):
        '''Collapses runs of at least max_repeat_run consecutive identical cues to a single cue'''
        ret = cues[:]
        max_repeat_run = self.get_param('max_repeat_run', MAX_REPEAT_RUN)

        if max_repeat_run > 1:
            collapsed = []
            i = 0
            while i < len(cues):
                run_end = i
                while run_end + 1 < len(cues) and self._normalize(cues[run_end + 1]['segment']) == self._normalize(cues[i]['segment']):
                    run_end += 1
                run_length = run_end - i + 1
                if run_length >= max_repeat_run:
                    collapsed.append(cues[i])
                else:
                    collapsed.extend(cues[i:run_end + 1])
                i = run_end + 1
            ret = collapsed

        return ret

    def _split_cues(self, cues: list):
        '''Returns a (cues, split_count) tuple with the transcription items split into cue-sized pieces
        when the split_long_segments parameter is enabled (except when split is disabled, the cues are
        returned unchanged and split_count is 0)'''
        ret = (cues, 0)
        if self.get_param('split_long_segments', False):
            split_cues = []
            split_count = 0
            for item in cues:
                pieces = self._split_cue(item)
                if len(pieces) > 1:
                    split_count += 1
                split_cues.extend(pieces)
            ret = (split_cues, split_count)
        return ret

    def _split_cue(self, item: dict):
        '''Splits a transcription item into pieces of at most max_cue_chars characters, breakable at
        the sentence boundaries of the text and at word boundaries inside too long sentences, with the
        item duration distributed over the pieces proportionally to their number of characters'''
        ret = [item]
        pieces = self._split_text(item['segment'])
        if len(pieces) > 1:
            ret = self._allocate_pieces_time(item, pieces)
        return ret

    def _split_text(self, text: str):
        '''Splits a text into pieces of at most max_cue_chars characters, breakable at its sentence
        boundaries and at word boundaries inside too long sentences'''
        ret = []
        sentences = [sentence.strip() for sentence in re.split(r'(?<=[.!?;:])\s+', text.strip()) if sentence.strip()]
        for sentence in sentences:
            ret.extend(self._wrap_text(sentence))
        return ret or [text.strip()]

    def _wrap_text(self, text: str):
        '''Wraps a text into pieces of at most max_cue_chars characters, preferring a break after a
        comma, a semicolon or a filler word'''
        ret = []
        remaining = text
        while len(remaining) > self.get_param('max_cue_chars', MAX_CUE_CHARS):
            cut = self._find_cut_point(remaining)
            ret.append(remaining[:cut].strip())
            remaining = remaining[cut:].strip()
        if remaining:
            ret.append(remaining)
        return ret

    def _find_cut_point(self, text: str):
        '''Returns the index of the preferred word-break in a text too long for a single piece,
        the index of its end if no break is found'''
        ret = None
        best_separator_index = -1
        best_separator = None
        for separator in [', ', '; ', '-- ', ' and ', ' but ', ' that ']:
            separator_index = text.rfind(separator, 0, self.get_param('max_cue_chars', MAX_CUE_CHARS))
            if separator_index > best_separator_index:
                best_separator_index = separator_index
                best_separator = separator
        if best_separator:
            ret = best_separator_index + len(best_separator)
        else:
            space_index = text.rfind(' ', 0, self.get_param('max_cue_chars', MAX_CUE_CHARS))
            if space_index > -1:
                ret = space_index + 1
            else:
                ret = self.get_param('max_cue_chars', MAX_CUE_CHARS)
        return ret

    def _allocate_pieces_time(self, item: dict, pieces: list):
        '''Distributes the duration of a transcription item over its pieces proportionally to their
        number of characters, keeping the pieces in order'''
        ret = []
        total_chars = sum(len(piece) for piece in pieces)
        duration = item['end'] - item['start']
        start = item['start']
        for piece in pieces:
            piece_duration = duration * len(piece) / total_chars
            ret.append({'start': start, 'end': start + piece_duration, 'segment': piece})
            start += piece_duration
        return ret

    def _merge_tiny_cues(self, cues: list):
        '''Merges each surviving cue shorter than min_cue_words words into an adjacent cue, to avoid
        unreadable single-word subtitles; a merged cue keeps at most two lines of subtitles'''
        ret = cues
        if self.get_param('split_long_segments', False):
            max_merged_chars = 2 * self.get_param('max_cue_chars', MAX_CUE_CHARS)
            merged_cues = []
            for cue in cues:
                previous_cue = merged_cues[-1] if merged_cues else None
                if previous_cue and self._is_tiny_cue(cue) and self._can_merge(previous_cue, cue, max_merged_chars):
                    previous_cue['segment'] += ' ' + cue['segment']
                    previous_cue['end'] = cue['end']
                else:
                    merged_cues.append(dict(cue))
            if len(merged_cues) > 1 and self._is_tiny_cue(merged_cues[0]):
                if self._can_merge(merged_cues[0], merged_cues[1], max_merged_chars):
                    merged_cues[1]['segment'] = merged_cues[0]['segment'] + ' ' + merged_cues[1]['segment']
                    merged_cues[1]['start'] = merged_cues[0]['start']
                    del merged_cues[0]
            ret = merged_cues
        return ret

    def _can_merge(self, first: dict, second: dict, max_chars: int):
        '''Returns True if the two cues can be joined into a piece of at most max_chars characters'''
        ret = len(first['segment']) + 1 + len(second['segment']) <= max_chars
        return ret

    def _is_tiny_cue(self, cue: dict):
        '''Returns True if the cue is shorter than min_cue_words words'''
        ret = len(cue['segment'].split()) < self.get_param('min_cue_words', MIN_CUE_WORDS)
        return ret

    def _normalize(self, text: str) -> str:
        '''Returns the text lowered and stripped of non-alphanumeric characters, for duplicate detection'''
        ret = re.sub(r'[^a-z0-9 ]', '', text.lower()).strip()
        return ret

    def _generate_srt(self, cues: list, srt_path: Path):
        '''Converts transcription items into a srt subtitle file'''
        ret = None

        lines = []
        for i, item in enumerate(cues):
            lines.append(str(i + 1))
            lines.append(f'{self._get_srt_timestamp(item["start"])} --> {self._get_srt_timestamp(item["end"])}')
            lines.append(str(item["segment"]))
            lines.append('')
        srt_path.write_text('\n'.join(lines))

        return ret

    def _get_srt_timestamp(self, seconds: float) -> str:
        '''Converts a number of seconds into a srt timestamp (HH:MM:SS,mmm)'''
        ret = None

        total_milliseconds = round(float(seconds) * 1000)
        hours, remainder = divmod(total_milliseconds, 3600000)
        minutes, remainder = divmod(remainder, 60000)
        secs, milliseconds = divmod(remainder, 1000)
        ret = f'{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}'

        return ret
