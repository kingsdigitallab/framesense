from pathlib import Path
from ..scale_frames.operator import ScaleFrames
import re
import json
from datetime import datetime
import subprocess
import shutil

class ScaleFramesSSSabet(ScaleFrames):
    '''Shot scale classification from frames based on //github.com/sssabet/Shot_Type_Classification
    
    The model and code are borrowed from the following repository
    //github.com/sssabet/Shot_Type_Classification
    created by Saeed Shafiee Sabet.
    '''

    def _recognise_frame_scale(self, frame_file_path: Path):
        ret = ''

        current_time = datetime.now()
        iso_string = current_time.strftime("%Y-%m-%d-%M-%S-%f")

        image_file_name = 'img.jpg'

        shutil.copy2(
            frame_file_path, 
            self._get_operator_folder_path() / 'app' / image_file_name
        )

        command_args = [
            'python',
            'detect.py',
            image_file_name
        ]

        binding = None
        
        res = self._run_in_operator_container(command_args, binding, same_user=True)

        response = json.loads(res.stdout)
        error = response.get('error', '')
        if not error:
            ret = response.get('class', '')
            # print(ret)

        return ret
