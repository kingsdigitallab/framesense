# Script created by opencode:e-research/arc:apex
# New operator sub_clips_ffmpeg burning the subtitles of the srt file of a clip (output of transcription_vad_sub) onto clips; clips without that file are ignored.

from pathlib import Path
from ..base.operator import Operator

SUB_SUFFIX = '-sub'
TMP_SUFFIX = '-tmp'
CONTAINER_DATA_PATH = Path('/data')
# characters which are special to the FFMPEG filter syntax
FILTER_SPECIAL_CHARACTERS = ['\\', ':', ',', "'"]

class SubClipsFFMPEG(Operator):
    '''Burn the subtitles of an srt file onto clips using FFMPEG'''

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
            'linked': 0,
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

        self._log(f"subtitled clips created: {stats['created']}; already existing: {stats['existing']}; clips skipped: {stats['skipped']}; srt files not found: {stats['missing']}; empty srt symlinked: {stats['linked']}")

        return ret

    def _sub_clip(self, clip_path: Path, collection_path: Path):
        '''Burns the subtitles of a clip into a new clip, placed in its own folder next to the original one.
        Returns the name of the stats counter the clip has been processed with, None if not processed'''
        ret = None

        if not self._is_path_selected(clip_path):
            return ret

        srt_path = clip_path.with_suffix('.srt')

        if not srt_path.exists():
            ret = 'missing'
        else:
            sub_folder_path = clip_path.parent.with_name(clip_path.parent.name + SUB_SUFFIX)
            subbed_clip_path = sub_folder_path / f'{clip_path.stem}{SUB_SUFFIX}{clip_path.suffix}'

            if not srt_path.read_text().strip():
                # no subtitle cues to burn, symlink the clip as is
                ret = self._link_empty_clip(clip_path, sub_folder_path, subbed_clip_path)
            else:
                if self._is_redo() or not subbed_clip_path.exists():
                    sub_folder_path.mkdir(exist_ok=True)

                    # written to a temporary file in the same folder, renamed on completion, so that the operation is atomic
                    subbed_clip_tmp_path = sub_folder_path / f'{clip_path.stem}{SUB_SUFFIX}{TMP_SUFFIX}{clip_path.suffix}'

                    self._log(subbed_clip_path)

                    command = [
                        "ffmpeg",
                        "-i", clip_path,
                        "-c:v", str(self.get_param("video_codec")),
                        "-crf", str(self.get_param("crf")),
                        "-preset", str(self.get_param("preset")),
                        "-c:a", "copy",
                        "-vf", self._get_subtitles_filter(srt_path, collection_path),
                        "-y",
                        subbed_clip_tmp_path
                    ]
                    res = self._run_in_operator_container(command, [collection_path, CONTAINER_DATA_PATH], same_user=True, skip=self._is_skip())

                    if res.returncode > 0:
                        subbed_clip_tmp_path.unlink(missing_ok=True)
                        self._warn(f'Subtitles not burned into clip: {clip_path}')
                        ret = 'skipped'
                    else:
                        subbed_clip_tmp_path.rename(subbed_clip_path)
                        ret = 'created'
                else:
                    ret = 'existing'

        return ret

    def _link_empty_clip(self, clip_path: Path, sub_folder_path: Path, subbed_clip_path: Path):
        '''For a clip whose srt file is empty, symlinks the clip to a new clip in its own folder next to the original one.
        Returns the name of the stats counter the clip has been processed with'''
        ret = 'linked'

        if not self._is_redo() and subbed_clip_path.exists():
            ret = 'existing'
        else:
            sub_folder_path.mkdir(exist_ok=True)

            if self._is_redo():
                subbed_clip_path.unlink(missing_ok=True)

            self._log(subbed_clip_path)

            # relative symlink to the input clip, e.g. ../<clip>/<clip>.mp4
            subbed_clip_path.symlink_to(Path('..') / clip_path.parent.name / clip_path.name)

        return ret

    def _get_subtitles_filter(self, srt_path: Path, collection_path: Path) -> str:
        '''Returns the FFMPEG video filter burning an srt file into a clip, the srt path being translated into its container equivalent'''
        ret = None
        container_srt_path = CONTAINER_DATA_PATH / srt_path.relative_to(collection_path)
        force_style = ','.join([
            f'FontSize={self.get_param("font_size")}',
            f'FontName={self.get_param("font")}',
            f'Bold={self.get_param("bold")}',
            f'Outline={self.get_param("outline")}',
            f'Shadow={self.get_param("shadow")}',
            f'PrimaryColour={self.get_param("text_color")}',
            f'OutlineColour={self.get_param("outline_color")}',
            f'BackColour={self.get_param("shadow_color")}',
        ])
        ret = f"subtitles={self._escape_filter_path(container_srt_path)}:force_style='{force_style}'"
        return ret

    def _escape_filter_path(self, path: Path) -> str:
        '''Escapes the characters of a path which are special to the FFMPEG filter syntax'''
        ret = str(path)
        for character in FILTER_SPECIAL_CHARACTERS:
            ret = ret.replace(character, f'\\{character}')
        return ret

