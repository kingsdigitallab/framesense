from ..base.operator import Operator
from pathlib import Path
from importlib import import_module
import inspect

class Collections(Operator):
    '''List all collections'''

    def get_supported_arguments(self):
        ret = super().get_supported_arguments()
        ret['verbose'] = True
        return ret

    def _apply(self):
        ret = None

        for col in self.context['collections']:
            col_path = col["attributes"]["path"]
            is_dir = (col_path).is_dir()
            video_paths = []
            if is_dir:
                for video_path in col_path.iterdir():
                    if video_path.is_dir():
                        video_paths.append(video_path)
                col_summary = f'has {len(video_paths)} videos under {col_path}'
            else:
                col_summary = "NOT FOUND"
            print(col["id"], col_summary)

            if self._is_verbose():
                for video_path in sorted(video_paths):
                    print(f'  {video_path.name}')

        return ret
