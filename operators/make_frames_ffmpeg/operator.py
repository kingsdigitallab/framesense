from pathlib import Path
from ..base.operator import Operator
import re
import json
from datetime import datetime
import subprocess
from datetime import timedelta

class MakeFramesFFMPEG(Operator):
    '''Extract frames from shots using ffmpeg'''

    def get_supported_arguments(self):
        ret = super().get_supported_arguments()
        ret['filter'] = True
        ret['redo'] = True
        ret['parameters'] = True
        return ret

    def apply(self, *args, **kwargs):
        ret = super().apply(*args, **kwargs)

        for col in self.context['collections']:
            for shot_file_path in col['attributes']['path'].glob('**/shots/*/*.mp4'):
                self._make_frames(shot_file_path)

        return ret

    def _make_frames(self, shot_file_path: Path):           
        shot_folder_path = shot_file_path.parent

        if not self._is_path_selected(shot_file_path):
            return

        frame_file_paths = list(shot_folder_path.glob('*.jpg'))

        if self._is_redo():
            # remove existing frames .jpg and frames.json
            for frame_file_path in frame_file_paths:
                frame_file_path.unlink()
            frame_file_paths = []

            for frame_file_path in shot_folder_path.glob('frames.json'):
                frame_file_path.unlink()
        
        if frame_file_paths:
            return

        parameters = self._get_operator_parameters()
        print(shot_file_path)

        if parameters:
            # e.g. sample every 10th frame 
            # parameters should be 'select=not(mod(n\,10))'
            # ffmpeg -i input.mp4 -vf "select=not(mod(n\,10))" -vsync vfr 1_every_10/img_%03d.jpg
            # https://superuser.com/a/1274696
            # for 2 fps: 'fps=2'
            samples = [
                '-vf', parameters,
                '-vsync', 'vfr',
                shot_folder_path / '%04d.jpg'
            ]
        else:
            # take first, middle and last frames
            binding = [shot_folder_path, Path('/data')]
            command_args = [
                'ffprobe', 
                '-v', 'error', 
                '-select_streams', 'v:0', 
                '-count_frames',
                '-show_entries', 
                # TODO: nb_read_frames is accurate but slower than nb_frames
                'format=duration:stream=nb_frames', 
                '-of', 'json', 
                shot_file_path,
            ]
            res = self._run_in_operator_container(command_args, binding)
            
            '''
            {
                "programs": [

                ],
                "streams": [
                    {
                        "nb_read_frames": "30"
                    }
                ],
                "format": {
                    "duration": "1.250000"
                }
            }
            '''

            metadata = json.loads(res.stdout)
            duration_seconds = float(metadata['format']['duration'])

            # now get first, middle and last frames
            # TODO: improve that sampling
            samples = []
            # .99 or 1 won't match a frame
            places = [0, 0.5, .95]

            for i, place in enumerate(places):
                samples += [
                    '-ss',
                    str(timedelta(seconds=duration_seconds * place)),
                    '-vframes', '1',
                    shot_folder_path / f'{i+1:04d}.jpg'
                ]

        # ffmpeg -i input.mp4 -ss 00:00:10 -vframes 1 frame1.png -ss 00:00:20 -vframes 1 frame2.png -ss 00:00:30 -vframes 1 frame3.png
        binding = [shot_folder_path, Path('/data')]
        command_args = [
            'ffmpeg', 
            '-i', shot_file_path
        ] + samples
        # print(command_args)
        res = self._run_in_operator_container(command_args, binding, same_user=True)

