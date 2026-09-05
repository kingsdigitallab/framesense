from pathlib import Path
from ..base.operator import Operator
import json

CLIP_START_TIME_CODE = '00:00:00'

class ClipFullVideo(Operator):
    '''Create a clip covering the whole video by symlinking its video file'''

    def get_supported_arguments(self):
        ret = super().get_supported_arguments()
        ret['filter'] = True
        ret['redo'] = True
        return ret

    def _apply(self):
        ret = None

        for col in self.context['collections']:
            for video_folder_path in sorted(col['attributes']['path'].iterdir()):
                if not video_folder_path.is_dir(): continue
                video_path = self._get_video_file_path(video_folder_path, direct_child_only=True)
                if video_path:
                    self._clip_full_video(video_path)

        return ret

    def _clip_full_video(self, video_path: Path):
        if not self._is_path_selected(video_path):
            return

        duration_seconds = self._get_video_duration_seconds(video_path)
        clip_name = f'{CLIP_START_TIME_CODE.replace(":", ".")}-{duration_seconds}'
        clip_folder_path = video_path.parent / clip_name
        clip_file_path = clip_folder_path / f'{clip_name}{video_path.suffix}'

        if self._is_redo():
            clip_file_path.unlink(missing_ok=True)

        if not clip_file_path.exists():
            if not clip_folder_path.exists():
                clip_folder_path.mkdir()

            self._log(f'create new full clip {clip_file_path} symlinking to video {video_path.name}')
            clip_file_path.symlink_to(Path('..') / video_path.name)

    def _get_video_duration_seconds(self, video_path: Path) -> int:
        ret = 0

        binding = [video_path.parent, Path('/data')]
        command_args = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'json',
            video_path,
        ]
        res = self._run_in_operator_container(command_args, binding)
        metadata = json.loads(res.stdout)
        ret = int(float(metadata['format']['duration']))

        return ret
