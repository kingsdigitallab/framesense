from pathlib import Path
from ..base.operator import Operator
import json

CLIP_START_TIME_CODE = '00:00:00'
CLIP_NAME_SUFFIX = '-full'

class ClipFullVideo(Operator):
    '''Create a clip covering the whole video by symlinking its video file'''

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
        }

        for col in self.context['collections']:
            for video_folder_path in sorted(col['attributes']['path'].iterdir()):
                if not video_folder_path.is_dir(): continue
                video_path = self._get_video_file_path(video_folder_path, direct_child_only=True)
                if video_path:
                    outcome = self._clip_full_video(video_path)
                    if outcome:
                        stats[outcome] += 1

        self._log(f"clips created: {stats['created']}; already existing: {stats['existing']}; videos skipped: {stats['skipped']}")

        return ret

    def _clip_full_video(self, video_path: Path):
        ret = None

        if not self._is_path_selected(video_path):
            return ret

        duration_seconds = self._get_video_duration_seconds(video_path)

        if duration_seconds is None:
            self._warn(f'Could not read the duration of the video, clip not created: {video_path}')
            ret = 'skipped'
        else:
            clip_name = f'{CLIP_START_TIME_CODE.replace(":", ".")}-{duration_seconds}{CLIP_NAME_SUFFIX}'
            clip_folder_path = video_path.parent / clip_name
            clip_file_path = clip_folder_path / f'{clip_name}{video_path.suffix}'

            if self._is_redo():
                clip_file_path.unlink(missing_ok=True)

            if clip_file_path.exists():
                ret = 'existing'
            else:
                if not clip_folder_path.exists():
                    clip_folder_path.mkdir()

                self._log(f'create new full clip {clip_file_path} symlinking to video {video_path.name}')
                clip_file_path.symlink_to(Path('..') / video_path.name)
                ret = 'created'

        return ret

    def _get_video_duration_seconds(self, video_path: Path):
        ret = None

        binding = [video_path.parent, Path('/data')]
        command_args = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'json',
            video_path,
        ]
        res = self._run_in_operator_container(command_args, binding, skip=self._is_skip())

        if res.returncode == 0:
            try:
                metadata = json.loads(res.stdout)
                ret = int(float(metadata['format']['duration']))
            except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                pass

        return ret
