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

        self._log(f"srt files created: {stats['created']}; stale recreated: {stats['stale']}; already existing: {stats['existing']}; clips skipped: {stats['skipped']}; transcriptions not found: {stats['missing']}; without voice segments: {stats['unfiltered']}; short-overlap cues dropped: {stats['short_overlap_dropped']}; repeated cues collapsed: {stats['repeated_dropped']}")

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

                    if voice_segments_path.exists():
                        voice_segments = self.read_json(voice_segments_path)
                        overlapping = [item for item in transcription if self._get_max_overlap(item, voice_segments) > 0]
                        cues = [item for item in overlapping if self._is_speech(item, voice_segments)]
                        dropped_counts['short_overlap_dropped'] = len(overlapping) - len(cues)
                        collapsed_cues = self._collapse_repeats(cues)
                        dropped_counts['repeated_dropped'] = len(cues) - len(collapsed_cues)
                        cues = collapsed_cues
                    else:
                        # detect_speech_vad has not been run on the clip: all the segments are kept
                        is_unfiltered = True
                        cues = transcription

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
