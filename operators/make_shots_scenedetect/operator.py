from pathlib import Path
from ..base.operator import Operator
import re
import json
from datetime import datetime
import subprocess
import shutil

class MakeShotsSceneDetect(Operator):
    '''Extract shots from clips using PySceneDetect'''

    def get_supported_arguments(self):
        ret = super().get_supported_arguments()
        ret['redo'] = True
        ret['filter'] = True
        ret['parameters'] = True
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
                                self._make_shots(clip_path)

        return ret

    def _make_shots(self, clip_path: Path):
        if not self._is_path_selected(clip_path):
            return

        shots_folder_path = clip_path.parent / 'shots'
        shots_folder_tmp_path = clip_path.parent / 'shots.tmp'
                
        if self._is_redo():
            if shots_folder_path.exists():
                shutil.rmtree(shots_folder_path)

        if shots_folder_path.exists():
            return

        if shots_folder_tmp_path.exists():
            shutil.rmtree(shots_folder_tmp_path)
        
        print(f'{clip_path}')

        shots_folder_tmp_path.mkdir(exist_ok=True)

        detection_parameters = ['detect-adaptive']
        framesense_parameters = self._get_operator_parameters()
        if framesense_parameters:
            detection_parameters = re.split(r'\s+', framesense_parameters)

        binding = [clip_path.parent, Path('/data')]
        command_args = [
            'scenedetect',
            '--input', clip_path,
            '--output', shots_folder_tmp_path
        ] + detection_parameters + [
            'split-video',  # creates a mp4 file per shot
            'list-scenes', # creates a CSV files with one row per shot
        ]
        self._run_in_operator_container(command_args, binding, same_user=True)

        # rename and move the files
        # 1. 00.58.16-298-Scene-003.mp4 => 003/shot.mp4
        for shot_file_path in shots_folder_tmp_path.glob('*.mp4'):
            match = re.findall(r'Scene-(\d+)\.mp4$', shot_file_path.name)
            if not match: continue
            shot_index = match[0]
            shot_folder_path = shots_folder_tmp_path / shot_index
            shot_folder_path.mkdir(exist_ok=True)

            new_shot_file_path = shot_folder_path / 'shot.mp4'
            shot_file_path.rename(new_shot_file_path)
            
        # 2. 00.58.16-298-Scenes.csv => shots.csv
        # TODO
        for csv_path in shots_folder_tmp_path.glob('*-Scenes.csv'):
            csv_path.rename(shots_folder_tmp_path / 'shots.csv')

        # ensure the whole operation is atomic
        shots_folder_tmp_path.rename(shots_folder_path)
