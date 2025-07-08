from pathlib import Path
from ..scale_frames.operator import ScaleFrames
import re
import json
from datetime import datetime
import subprocess
import shutil
import time

class ScaleFramesSSSabet(ScaleFrames):
    '''Shot scale classification from frames based on //github.com/sssabet/Shot_Type_Classification
    
    The model and code are borrowed from the following repository
    //github.com/sssabet/Shot_Type_Classification
    created by Saeed Shafiee Sabet.
    '''

    def apply(self, *args, **kwargs):
        self.collection_path = None
        ret = super().apply(*args, **kwargs)
        self._stop_service()

    def _recognise_frame_scale(self, frame_file_path: Path, collection_path: Path):
        ret = ''

        # current_time = datetime.now()
        # iso_string = current_time.strftime("%Y-%m-%d-%M-%S-%f")

        binding = [
            collection_path, 
            '/data'
        ]

        command_args = [
            'python',
            'detect.py',
            'serve'
        ]

        if self.collection_path != str(collection_path):
            self._start_service_in_operator_container(command_args, binding, same_user=True, port_mapping=[5000, 5000], wait_for_message='Serving Flask app')
            self.collection_path = str(collection_path)

        # send request to localhost:5000/detect?image_path=frame_file_path

        # command_args = [
        #     'python',
        #     'detect.py',
        #     frame_file_path
        # ]

        # res = self._run_in_operator_container(command_args, binding, same_user=True)

        # response = json.loads(res.stdout)

        frame_file_path_in_container = binding[1] / frame_file_path.relative_to(binding[0])
        
        response = self._fetch_json(f'http://localhost:5000/detect?image_path={frame_file_path_in_container}')

        error = response.get('error', '')
        if not error:
            ret = response.get('class', '')
            # print(ret)

        return ret

    def _get_scale_attribute_name(self):
        '''The name of the attribute written by this operator in the frames.json file'''
        return 'scale_sssabet'
