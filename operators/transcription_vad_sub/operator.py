# Script created by opencode:e-research/arc:apex
# Prompt: create a new operator transcription_vad_sub which takes a clip X/transcription.json,
# keeps only the segments overlapping a voice segment of X/voice_segments.json
# (or all the segments if that file is absent) and writes X/X.srt.

from pathlib import Path
from ..base.operator import Operator

TRANSCRIPTION_FILE_NAME = 'transcription.json'
VOICE_SEGMENTS_FILE_NAME = 'voice_segments.json'
# folders of the clips subtitled by sub_clips_ffmpeg, ignored by this operator
SUB_SUFFIX = '-sub'


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
            'skipped': 0,
            'missing': 0,
            'unfiltered': 0,
        }

        for col in self.context['collections']:
            for video_folder_path in sorted(col['attributes']['path'].iterdir()):
                if video_folder_path.is_dir():
                    for clip_folder_path in sorted(video_folder_path.iterdir()):
                        # do not process the folders of subtitled clips created by sub_clips_ffmpeg
                        if clip_folder_path.is_dir() and not clip_folder_path.name.endswith(SUB_SUFFIX):
                            clip_path = self._get_video_file_path(clip_folder_path)
                            if clip_path:
                                outcome = self._write_srt(clip_path)
                                if outcome:
                                    stats[outcome] += 1

        self._log(f"srt files created: {stats['created']}; already existing: {stats['existing']}; clips skipped: {stats['skipped']}; transcriptions not found: {stats['missing']}; without voice segments: {stats['unfiltered']}")

        return ret

    def _write_srt(self, clip_path: Path):
        '''Writes the voice-filtered transcription of a clip into a srt file.
        Returns the name of the stats counter the clip has been processed with, None if not processed'''
        ret = None

        if not self._is_path_selected(clip_path):
            return ret

        transcription_path = clip_path.parent / TRANSCRIPTION_FILE_NAME

        if not transcription_path.exists():
            self._warn(f'Input transcription not found: {transcription_path}')
            ret = 'missing'
        else:
            srt_path = clip_path.with_suffix('.srt')

            if self._is_redo() or not srt_path.exists():
                is_unfiltered = False
                try:
                    transcription = self.read_json(transcription_path)

                    voice_segments_path = clip_path.parent / VOICE_SEGMENTS_FILE_NAME
                    if voice_segments_path.exists():
                        voice_segments = self.read_json(voice_segments_path)
                        cues = [item for item in transcription if self._is_speech(item, voice_segments)]
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
                    else:
                        ret = 'created'
            else:
                ret = 'existing'

        return ret

    def _is_speech(self, item: dict, voice_segments: list):
        '''Returns True if the transcription item overlaps one of the voice segments'''
        ret = False

        for voice_segment in voice_segments:
            start = max(item['start'], voice_segment['start'])
            end = min(item['end'], voice_segment['end'])
            if end > start:
                ret = True
                break

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
