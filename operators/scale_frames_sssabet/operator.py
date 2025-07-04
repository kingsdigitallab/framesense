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
        ret = 'CS'
        return ret
