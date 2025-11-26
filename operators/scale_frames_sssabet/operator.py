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

    def _recognise_frame_scale(self, frame_file_path: Path, collection_path: Path):
        # TODO: error management
        response = self._call_service_processor(frame_file_path, collection_path)
        return response['result']
