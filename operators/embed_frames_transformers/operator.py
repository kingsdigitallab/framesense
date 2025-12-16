from pathlib import Path
from ..base.operator import Operator
import re
import json
import datetime
import hashlib

class EmbedFramesTransformers(Operator):
    '''Generate a vector from a frame using an embedding model'''

    def get_supported_arguments(self):
        ret = super().get_supported_arguments()
        ret['redo'] = True
        ret['filter'] = True
        return ret

    def _apply(self):
        ret = None

        for col in self.context['collections']:
            collection_path = col['attributes']['path']
            for frames_folder_path in sorted(collection_path.glob('**/shots/*/')):
                self._process_frame(frames_folder_path, collection_path)

        return ret

    def _process_frame(self, frames_folder_path: Path, collection_path: Path):
        frames_meta_path = Path(frames_folder_path / 'frames.json')
        frames_meta_content = self._read_data_file(frames_meta_path, is_data_dict=True)
        frames_data = frames_meta_content['data']
        
        frame_file_paths = list(frames_folder_path.glob('*.jpg'))

        has_changed = False
        for frame_file_path in frame_file_paths:
            if self.get_param('frame_filter') not in str(frame_file_path):
                continue

            if not self._is_path_selected(frame_file_path):
                return

            data_key = 'embedding'

            frame_id = re.sub(r'^(\d+).*$', r'\1', frame_file_path.name)
            frame_data = frames_data.get(frame_id, None)
            if not frame_data:
                frame_data = {}
                frames_data[frame_id] = frame_data

            prompt_hash = self.short_hash('; '.join([
                str(p)
                for p
                in [
                    self.get_param('model'), 
                    # self.get_param('context_length'),
                    # self.get_param('seed'),
                ]
            ]))

            if not self._is_redo() and frame_data.get(data_key, {}).get('prompt_hash', None) == prompt_hash:
                # we already got that answer, skip
                continue

            answer = '[]'
            res = self._call_service_processor(frame_file_path, collection_path)
            if res['error']:
                self._error(res['error'])

            # res = self._run_in_operator_container(command_args, binding, share_network=True)
            # response = json.loads(res.stdout)
            # TODO: check for errors
            answer = res['result']

            frame_data[data_key] = {
                'value': self._parse_dirty_json(answer),
                'operator': self._get_operator_name(),
                'model': self.get_param('model'),
                # 'context_length': self.get_param('context_length'),
                'seed': self.get_param('seed'),
                'updated': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'prompt_hash': prompt_hash,
            }
            has_changed = True
                
        if has_changed:
            self._write_data_file(frames_meta_path, frames_meta_content)

    def short_hash(self, s, length=8):
        hash_object = hashlib.sha256(s.encode('utf-8'))
        return hash_object.hexdigest()[:length]


    def get_hhmmss(self, seconds):
        hours = int(seconds // 3600)
        seconds %= 3600
        minutes = int(seconds // 60)
        seconds %= 60
        return f"{hours:02d}:{minutes:02d}:{int(seconds):02d}"
