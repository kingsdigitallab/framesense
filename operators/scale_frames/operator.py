from abc import ABC, abstractmethod
from pathlib import Path
from ..base.operator import Operator
import re
import json
from datetime import datetime
import subprocess
import shutil

class ScaleFrames(Operator):
    '''Shot scale classification from frames'''

    def get_supported_arguments(self):
        ret = super().get_supported_arguments()
        ret['redo'] = True
        ret['filter'] = True
        return ret

    def _apply(self):
        ret = None

        for col in self.context['collections']:
            collection_path = col['attributes']['path']
            for frames_folder_path in collection_path.glob('**/shots/*/'):
                self._write_frames_scale(frames_folder_path, collection_path)

        return ret

    def _write_frames_scale(self, frames_folder_path: Path, collection_path: Path):
        scale_attribute_name = 'shot_scale'

        if not self._is_path_selected(frames_folder_path):
            return
        
        frames_meta_path = Path(frames_folder_path / 'frames.json')
        frames_meta_content = self._read_data_file(frames_meta_path, is_data_dict=True)
        frames_data = frames_meta_content['data']
        if not isinstance(frames_data, dict):
            frames_data = {}
            frames_meta_content['data'] = frames_data

        frame_file_paths = list(frames_folder_path.glob('*.jpg'))
        for frame_file_path in frame_file_paths:
            frame_id = re.sub(r'^(\d+).*$', r'\1', frame_file_path.name)
            frame_data = frames_data.get(frame_id, None)
            if not frame_data:
                frame_data = {}
                frames_data[frame_id] = frame_data

            if self._is_redo() or not frame_data.get(scale_attribute_name, None):
                res = self._recognise_frame_scale(frame_file_path, collection_path)
                frame_data['scale_attribute_name'] = {
                    'value': res,
                    'operator': self._get_operator_name(),
                    'method': '',
                }

        self._write_data_file(frames_meta_path, frames_meta_content)
                
    @abstractmethod
    def _recognise_frame_scale(self, frame_file_path: Path, collection_path: Path):
        ret = ''
        return ret
