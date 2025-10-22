from pathlib import Path
from ..base.operator import Operator
import re
import json
from datetime import datetime
import subprocess
import shutil

# quality of mp3 output from 0 (poorest) to 9 (best)
SOUND_QUALITY_DEFAULT = 4

class ExtractSoundFFMPEG(Operator):
    '''Extract sound from clips using FFMPEG'''

    def get_supported_arguments(self):
        ret = super().get_supported_arguments()
        ret['redo'] = True
        ret['filter'] = True
        return ret

    def apply(self, *args, **kwargs):
        ret = super().apply(*args, **kwargs)

        for col in self.context['collections']:
            for video_folder_path in col['attributes']['path'].iterdir():
                if video_folder_path.is_dir():
                    for clip_folder_path in video_folder_path.iterdir():
                        if clip_folder_path.is_dir():
                            clip_path = self._get_video_file_path(clip_folder_path)
                            if clip_path:
                                self._extract_sound(clip_path)

        return ret

    def _extract_sound(self, clip_path: Path):
        if not self._is_path_selected(clip_path):
            return

        sound_path = clip_path.with_suffix('.mp3')

        if self._is_redo() or not sound_path.exists():
            print(sound_path)
            command = [
                # "linuxserver/ffmpeg",
                "ffmpeg",
                "-i", clip_path,
                "-vn", 
                "-acodec", "libmp3lame",
                "-q:a", str(SOUND_QUALITY_DEFAULT),
                sound_path
            ]
            self._run_in_operator_container(command, [clip_path.parent, '/data'], same_user=True)
