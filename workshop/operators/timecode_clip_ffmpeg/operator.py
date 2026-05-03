'''
'''
from pathlib import Path
from ..base.operator import Operator
import json


class TimecodeClipFFMPEG(Operator):
    '''Overlay a running timecode to the top left corner of every frame of a clip'''

    def get_supported_arguments(self):
        ret = super().get_supported_arguments()

        # TODO: WORKSHOP EXERCISE

        return ret

    def _apply(self):
        ret = None

        # TODO: WORKSHOP EXERCISE

        return ret

    def _timecode_clip(self, clip_path: Path):
        # TODO: WORKSHOP EXERCISE
        return

    def _get_video_frame_rate(self, clip_path: Path) -> str:
        binding = [clip_path.parent, Path('/data')]
        command_args = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=r_frame_rate',
            '-of', 'json',
            clip_path,
        ]
        res = self._run_in_operator_container(command_args, binding)
        metadata = json.loads(res.stdout)
        rate_str = metadata['streams'][0]['r_frame_rate']
        num, den = rate_str.split('/')
        den = int(den)
        num = int(num)
        if den == 0:
            return '25'
        return str(round(num / den, 3))
