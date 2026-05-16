from ..base.operator import Operator
from pathlib import Path
from importlib import import_module
import inspect
import json

NO_VIDEO_FOLDER = 'NO VIDEO FOLDER'

class Annotations(Operator):
    '''List all annotation files'''

    def get_supported_arguments(self):
        ret = super().get_supported_arguments()
        ret['verbose'] = True
        return ret

    def _apply(self):
        ret = None
        
        for col in self.context['collections']:
            annotations_path = col["attributes"]["annotations_path"]
            self._log(f'{col["id"]} under {str(annotations_path)}')
            if not annotations_path:
                self._warn(f'  annotations_path not provided in collections.json')
                continue

            if not annotations_path.is_dir():
                self._warn(f'  annotations_path not found ({str(annotations_path)})')
                continue

            annotation_paths = list(annotations_path.glob('*.json'))

            if self._is_verbose():
                for annotation_path in annotation_paths:
                    video_name = str(annotation_path.relative_to(annotations_path)).replace('.json', '')
                    content = json.loads(annotation_path.read_text())
                    clips = content.get('clips', [])
                    
                    video_path = col['attributes']['path'] / video_name
                    match_message = ''
                    if not video_path.is_dir():
                        match_message = NO_VIDEO_FOLDER

                    self._log(f'  {len(clips):3} clips {match_message:15} "{annotation_path}"')

            self._log(f'  {len(annotation_paths)} annotation files')

        return ret