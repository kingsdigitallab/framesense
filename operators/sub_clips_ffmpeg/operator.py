# Script created by opencode:e-research/arc:apex
# New operator sub_clips_ffmpeg burning the subtitles of transcription.json (output of transcribe_speech_parakeet) onto clips; clips without that file are ignored.

from pathlib import Path
from ..base.operator import Operator

TRANSCRIPTION_FILE_NAME = 'transcription.json'
SRT_FILE_NAME = 'transcription.srt'
SUB_SUFFIX = '-sub'
CONTAINER_DATA_PATH = Path('/data')
# characters which are special to the FFMPEG filter syntax
FILTER_SPECIAL_CHARACTERS = ['\\', ':', ',', "'"]

class SubClipsFFMPEG(Operator):
    '''Burn the subtitles of a transcription file onto clips using FFMPEG'''

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
        }

        for col in self.context['collections']:
            collection_path = col['attributes']['path']
            for video_folder_path in sorted(collection_path.iterdir()):
                if video_folder_path.is_dir():
                    for clip_folder_path in sorted(video_folder_path.iterdir()):
                        # do not process the folders of subtitled clips created by this operator
                        if clip_folder_path.is_dir() and not clip_folder_path.name.endswith(SUB_SUFFIX):
                            clip_path = self._get_video_file_path(clip_folder_path)
                            if clip_path:
                                outcome = self._sub_clip(clip_path, collection_path)
                                if outcome:
                                    stats[outcome] += 1

        self._log(f"subtitled clips created: {stats['created']}; already existing: {stats['existing']}; clips skipped: {stats['skipped']}; transcriptions not found: {stats['missing']}")

        return ret

    def _sub_clip(self, clip_path: Path, collection_path: Path):
        '''Burns the subtitles of a clip into a new clip, placed in its own folder next to the original one.
        Returns the name of the stats counter the clip has been processed with, None if not processed'''
        ret = None

        if not self._is_path_selected(clip_path):
            return ret

        transcription_path = clip_path.parent / TRANSCRIPTION_FILE_NAME

        if not transcription_path.exists():
            ret = 'missing'
        else:
            sub_folder_path = clip_path.parent.with_name(clip_path.parent.name + SUB_SUFFIX)
            subbed_clip_path = sub_folder_path / f'{clip_path.stem}{SUB_SUFFIX}{clip_path.suffix}'

            if self._is_redo() or not subbed_clip_path.exists():
                srt_path = clip_path.parent / SRT_FILE_NAME
                self._generate_srt(transcription_path, srt_path)

                sub_folder_path.mkdir(exist_ok=True)

                self._log(subbed_clip_path)

                command = [
                    "ffmpeg",
                    "-i", clip_path,
                    "-c:a", "copy",
                    "-vf", self._get_subtitles_filter(srt_path, collection_path),
                    "-y",
                    subbed_clip_path
                ]
                res = self._run_in_operator_container(command, [collection_path, CONTAINER_DATA_PATH], same_user=True, skip=self._is_skip())

                if res.returncode > 0:
                    subbed_clip_path.unlink(missing_ok=True)
                    self._warn(f'Subtitles not burned into clip: {clip_path}')
                    ret = 'skipped'
                else:
                    ret = 'created'
            else:
                ret = 'existing'

        return ret

    def _get_subtitles_filter(self, srt_path: Path, collection_path: Path) -> str:
        '''Returns the FFMPEG video filter burning an srt file into a clip, the srt path being translated into its container equivalent'''
        ret = None
        container_srt_path = CONTAINER_DATA_PATH / srt_path.relative_to(collection_path)
        force_style = f'FontSize={self.get_param("font_size")},FontName={self.get_param("font")}'
        ret = f"subtitles={self._escape_filter_path(container_srt_path)}:force_style='{force_style}'"
        return ret

    def _escape_filter_path(self, path: Path) -> str:
        '''Escapes the characters of a path which are special to the FFMPEG filter syntax'''
        ret = str(path)
        for character in FILTER_SPECIAL_CHARACTERS:
            ret = ret.replace(character, f'\\{character}')
        return ret

    def _generate_srt(self, transcription_path: Path, srt_path: Path):
        '''Converts a transcription file into a srt subtitle file'''
        ret = None
        lines = []
        for i, item in enumerate(self.read_json(transcription_path)):
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
