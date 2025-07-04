from pathlib import Path
from ..make_clips.operator import MakeClips
import re
import json
from datetime import datetime
import subprocess

class MakeClipsFFMPEG(MakeClips):
    '''Extract clips from videos based on timecodes in annotation files'''

    def _sluggify(self, string):
        return re.sub(r'\W+', '-', str(string).lower()).strip('-')

    def _index_annotation_files(self):
        self.annotations_index = {}
        for col in self.context['collections']:
            annotations_path = col['attributes'].get('annotations_path', None)
            if not annotations_path: continue
            for annotation_path in annotations_path.glob('*.json'):
                annotation_hash = self._get_hash_from_path(col, annotation_path, True)
                self.annotations_index[annotation_hash] = annotation_path
        
        # print(self.annotations_index)

    def _get_hash_from_path(self, collection: dict, path: Path, has_extension=False) -> str:
        path = path.name
        if has_extension:
            path = path.rsplit('.', 1)[0]
        ret = f'{collection["id"]}:{self._sluggify(path)}'
        return ret

    def apply(self, *args, **kwargs):
        ret = super().apply(*args, **kwargs)
        
        self._index_annotation_files()

        for col in self.context['collections']:
            for video_folder_path in col['attributes']['path'].iterdir():
                if video_folder_path.is_dir():
                    hash = self._get_hash_from_path(col, video_folder_path)
                    annotations_path = self.annotations_index.get(hash, None)
                    if annotations_path:
                        for annotation in self._read_annotations(annotations_path):
                            self._make_clip(annotation, video_folder_path)

        return ret

    def _make_clip(self, annotation, video_folder_path):
        clip_info = self._get_annotation_info(annotation, video_folder_path)
        if not clip_info: return

        video_path = self._get_video_file_path(video_folder_path)
        if not video_path: return

        if not clip_info['path'].parent.exists():
            clip_info['path'].parent.mkdir()

        if not clip_info['path'].exists():
            command = [
                # "linuxserver/ffmpeg",
                "ffmpeg",
                "-ss", clip_info['start'],
                "-t", str(clip_info['duration']),
                "-i", video_path,
                clip_info['path']
            ]
            # self._run_in_container(command, [video_folder_path, '/config'])
            self._run_in_operator_container(command, [video_folder_path, '/config'])

    def _get_annotation_info(self, annotation, video_folder_path):
        ret = None

        time_codes_str = [
            annotation.get(k, '').strip()
            for k in ['startTime', 'endTime']
        ]

        if all([re.match(r'\d\d:\d\d:\d\d', tc) for tc in time_codes_str]):
            time_codes = [
                datetime.strptime(tc, "%H:%M:%S")
                for tc in time_codes_str
            ]
            duration_seconds = int((time_codes[1] - time_codes[0]).total_seconds())
            name = f'{time_codes_str[0].replace(":", ".")}-{duration_seconds}'
            ret = {
                'start': time_codes_str[0],
                'duration': duration_seconds,
                'name': name,
                'path': video_folder_path / name / f'{name}.mp4'
            }
        else:
            # TODO: report the file
            print(f'WARNING: invalid timecode format in annotation file, plase used HH:MM:SS.')

        return ret

    def _read_annotations(self, annotation_path: Path) -> [dict]:
        ret = []
        try:
            res = json.loads(annotation_path.read_text())
            if res:
                ret = res.get('clips', [])
        except json.decoder.JSONDecodeError:
            print(f'WARNING: invalid json format in annotation file {annotation_path}')
        return ret

