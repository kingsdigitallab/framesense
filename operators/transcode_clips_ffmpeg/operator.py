from pathlib import Path
from ..base.operator import Operator
import re
import json
from datetime import datetime
import subprocess
import shutil

class TranscodeClipsFFMPEG(Operator):
    '''Convert a clip file to another video format'''

    def get_supported_arguments(self):
        ret = super().get_supported_arguments()
        ret['redo'] = True
        ret['filter'] = True
        return ret

    def _apply(self):
        ret = None

        for col in self.context['collections']:
            for video_folder_path in col['attributes']['path'].iterdir():
                if video_folder_path.is_dir():
                    for clip_folder_path in video_folder_path.iterdir():
                        if clip_folder_path.is_dir():
                            clip_path = self._get_video_file_path(clip_folder_path)
                            if clip_path:
                                self._transcode_clip(clip_path)

        return ret

    def _transcode_clip(self, clip_path: Path):
        if not self._is_path_selected(clip_path):
            return

        command_str = self.get_param('command').strip()
        # TODO: find a more robust method to extract ext
        output_extension = re.sub(r'^.*?(\.[^.]+)$', r'\1', command_str)
        transcoded_path = Path(str(clip_path.with_suffix('')) + output_extension)

        if self._is_redo() or not transcoded_path.exists():
            self._log(transcoded_path)
            command = re.split(r'\s+', command_str)
            def replace(p):
                ret = p
                ret = ret.replace('{input}', str(clip_path))
                ret = ret.replace('{output}', str(clip_path.with_suffix('')))
                if ret != p:
                    ret = Path(ret)
                return ret

            command = [
                replace(p)
                for p 
                in command
            ]
            self._run_in_operator_container(command, [clip_path.parent, '/data'], same_user=True)
