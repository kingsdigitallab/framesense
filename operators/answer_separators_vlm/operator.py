# Script created by opencode:e-research/arc:apex
# Prompt: create a FrameSense operator inheriting from answer_videos_vlm that splits a video
# into overlapping chunks, asks a VLM for the separators between distinct programmes found in
# each chunk, and merges all chunk answers into video_answers.json.

from pathlib import Path
# the parent class is imported through its module, not bound directly in this module:
# the operator discovery picks the first concrete Operator class found in the module,
# and a directly imported concrete parent (such as AnswerVideosVLM) would shadow this operator
from ..answer_videos_vlm import operator as answer_videos_vlm_operator
import re
import json

CHUNKS_FOLDER_NAME = 'chunks'
CHUNK_FILE_NAME_TEMPLATE = '{start:08d}-{end:08d}.mp4'
CHUNK_VIDEO_CODEC = 'libx264'
CHUNK_VIDEO_PRESET = 'veryfast'
CHUNK_VIDEO_CRF = '28'
CHUNK_AUDIO_CODEC = 'aac'
# two neighbouring chunks both see the separators located in their overlapping region;
# entries found closer than this many seconds apart are considered to be the same separator
SEPARATOR_MERGE_TOLERANCE_SECS = 10

CHUNK_PROMPT_SUFFIX = '''The video is an excerpt of {duration_secs} seconds taken from a longer recording.
All timecodes must be given relative to the first frame of the excerpt: the first frame is at 00:00:00.
A separator truncated by the beginning or the end of the excerpt must be listed too, covering its visible part only.'''


class AnswerSeparatorsVLM(answer_videos_vlm_operator.AnswerVideosVLM):
    '''Split a video into overlapping chunks and let a VLM behind an openai-compatible API list the separators between distinct programmes'''

    def set_context(self, context):
        # chunks already cut during the current run, so that -r does not cut them again
        self.cut_chunk_paths = set()
        super().set_context(context)

    def _get_response_from_model(self, video_path, collection_path):
        ret = {
            'error': '',
            'result': [],
            'payload': {},
            'usage': {},
            'stats': {},
        }

        chunk_duration_secs = int(self.get_param('chunk_duration_secs'))
        chunk_overlap_secs = int(self.get_param('chunk_overlap_secs'))

        if chunk_overlap_secs < 0 or chunk_duration_secs <= chunk_overlap_secs:
            self._error(f'Invalid chunking parameters: chunk_duration_secs ({chunk_duration_secs}) must be greater than chunk_overlap_secs ({chunk_overlap_secs}).')

        video_duration_secs = self._get_video_duration_seconds(video_path)
        if video_duration_secs is None:
            self._error(f'Could not read the duration of the video: {video_path}')

        chunks = self._compute_chunks(video_duration_secs, chunk_duration_secs, chunk_overlap_secs)
        self._log(f'{video_path.name}: {len(chunks)} chunks of up to {chunk_duration_secs} s. with {chunk_overlap_secs} s. of overlap')

        base_prompt = self.get_param('prompt')

        separators = []
        chunks_info = []
        usage = {}
        stats = {
            'chunks': len(chunks),
            'duration_seconds': 0.0,
        }

        for i, chunk in enumerate(chunks):
            start_secs, end_secs = chunk

            chunk_info = {
                'start': self.get_hhmmss(start_secs),
                'end': self.get_hhmmss(end_secs),
                'file': '',
                'error': '',
            }
            chunks_info.append(chunk_info)

            chunk_path = self._make_chunk(video_path, start_secs, end_secs)
            if chunk_path is None:
                chunk_info['error'] = f'Could not create the chunk {self.get_hhmmss(start_secs)}-{self.get_hhmmss(end_secs)}'
                ret['error'] = chunk_info['error']
                break

            chunk_info['file'] = str(chunk_path.relative_to(video_path.parent))

            self._log(f'{video_path.name}: chunk {i + 1}/{len(chunks)} ({self.get_hhmmss(start_secs)}-{self.get_hhmmss(end_secs)})')

            chunk_prompt = base_prompt + '\n\n' + CHUNK_PROMPT_SUFFIX.format(duration_secs=end_secs - start_secs)
            self.set_param('prompt', chunk_prompt)

            response = self.send_prompt_to_openai_api_from_params(chunk_path, collection_path)

            if response['error']:
                chunk_info['error'] = response['error']
                ret['error'] = f'Chunk {self.get_hhmmss(start_secs)}-{self.get_hhmmss(end_secs)}: {response["error"]}'
                break

            ret['payload'] = response.get('payload', {})

            chunk_separators, chunk_error = self._get_chunk_separators(response, start_secs)
            chunk_info['error'] = chunk_error
            separators += chunk_separators

            for k, v in response.get('usage', {}).items():
                # usage[k] = usage.get(k, 0) 
                if isinstance(v, int):
                    usage[k] = usage.get(k, 0) + v

            stats['duration_seconds'] += response.get('stats', {}).get('duration_seconds', 0.0)

        ret['stats'] = dict(stats, chunks=chunks_info)

        if not ret['error']:
            ret['result'] = self._format_separators(self._merge_separators(separators))
            ret['usage'] = usage

        return ret

    def _compute_chunks(self, video_duration_secs: int, chunk_duration_secs: int, chunk_overlap_secs: int) -> list:
        '''Returns the (start, end) timecodes in seconds of the chunks covering the whole video, consecutive chunks overlapping by chunk_overlap_secs'''
        ret = []

        step_secs = chunk_duration_secs - chunk_overlap_secs

        start_secs = 0
        while True:
            end_secs = min(start_secs + chunk_duration_secs, video_duration_secs)
            ret.append((start_secs, end_secs))
            if end_secs >= video_duration_secs:
                break
            start_secs += step_secs

        return ret

    def _get_video_duration_seconds(self, video_path: Path):
        '''Returns the duration of the video in seconds, None if it could not be read'''
        ret = None

        binding = [video_path.parent, Path('/data')]
        command_args = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'json',
            video_path,
        ]
        res = self._run_in_operator_container(command_args, binding)

        if res and res.returncode == 0:
            try:
                metadata = json.loads(res.stdout)
                ret = int(float(metadata['format']['duration']))
            except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                pass

        return ret

    def _make_chunk(self, video_path: Path, start_secs: int, end_secs: int):
        '''Cuts the chunk of the video with ffmpeg and returns its path, None if it failed. An existing chunk is reused, except on -r.'''
        ret = None

        chunks_folder_path = video_path.parent / CHUNKS_FOLDER_NAME
        if not chunks_folder_path.exists():
            chunks_folder_path.mkdir()

        chunk_path = chunks_folder_path / CHUNK_FILE_NAME_TEMPLATE.format(start=start_secs, end=end_secs)

        # TODO: uncomment. Temporarily commented to avoid redoing chunks just b/c we redo prompts
        if self._is_redo() and chunk_path not in self.cut_chunk_paths:
            chunk_path.unlink(missing_ok=True)

        self.cut_chunk_paths.add(chunk_path)

        if not chunk_path.exists():
            command_args = [
                'ffmpeg',
                '-y',
                '-ss', str(start_secs),
                '-i', video_path,
                '-t', str(end_secs - start_secs),
                '-vf', f"fps={self.get_param('fps', 2)}", # doesn't save much space, but saves 30% time
                '-c:v', CHUNK_VIDEO_CODEC,
                '-preset', CHUNK_VIDEO_PRESET,
                '-crf', CHUNK_VIDEO_CRF,
                # '-c:a', CHUNK_AUDIO_CODEC, # audio not needed beause VML doesn't hear
                chunk_path,
            ]
            self._run_in_operator_container(command_args, [video_path.parent, Path('/data')], same_user=True)

        if chunk_path.exists():
            ret = chunk_path

        return ret

    def _get_chunk_separators(self, response: dict, start_secs: int) -> tuple:
        '''Returns the separators listed in a chunk answer, with timecodes converted to seconds relative to the full video, and the description of the issues found in the answer ('' if none)'''
        ret = []
        errors = []

        answer = self._parse_dirty_json(response['result'])

        if isinstance(answer, dict):
            # some models wrap the list into an object despite the prompt
            lists = [v for v in answer.values() if isinstance(v, list)]
            answer = lists[0] if lists else None

        if not isinstance(answer, list):
            errors.append('No list of separators could be parsed from the model answer')
            self._warn(f'No list of separators could be parsed from the model answer, chunk ignored ({self.get_hhmmss(start_secs)}): {response["result"]}')
            answer = []

        for entry in answer:
            separator, entry_error = self._get_separator(entry, start_secs)
            if entry_error:
                errors.append(entry_error)
            if separator:
                ret.append(separator)

        return ret, '; '.join(errors)

    def _get_separator(self, entry, start_secs: int) -> tuple:
        '''Returns a separator with timecodes in seconds relative to the full video (None if the entry is invalid) and the description of the issue with the entry ('' if the entry is valid)'''
        ret = (None, '')
        error = ''

        if not isinstance(entry, dict):
            error = f'Separator entry is not an object, ignored: {entry}'
        else:
            start = self._get_seconds_from_timecode(entry.get('start', None))
            end = self._get_seconds_from_timecode(entry.get('end', None))
            tag = str(entry.get('tag', '')).strip()

            if start is None or end is None:
                error = f'Separator entry with missing or invalid timecodes, ignored: {entry}'
            elif end < start:
                error = f'Separator entry ending before it starts, ignored: {entry}'
            else:
                ret = ({
                    'start': start_secs + start,
                    'end': start_secs + end,
                    'tag': tag,
                }, '')

        if error:
            self._warn(error)
            ret = (None, error)

        return ret

    def _get_seconds_from_timecode(self, timecode):
        '''Converts a timecode into seconds; accepts HH:MM:SS, MM:SS or plain seconds; None if invalid'''
        ret = None

        if isinstance(timecode, (int, float)):
            ret = int(timecode)
        else:
            match = re.match(r'^\s*(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:[.,]\d+)?\s*$', str(timecode))
            if match:
                ret = int(match.group(1) or 0) * 3600 + int(match.group(2)) * 60 + int(match.group(3))

        return ret

    def _merge_separators(self, separators: list) -> list:
        '''Merges the separators found twice: those located in the overlapping region of two neighbouring chunks are reported by both chunks'''
        ret = []

        for separator in sorted(separators, key=lambda s: s['start']):
            if ret and (separator['start'] - ret[-1]['start']) <= SEPARATOR_MERGE_TOLERANCE_SECS:
                # keep the longer of the two versions, as it is less likely to be truncated at a chunk boundary
                if (separator['end'] - separator['start']) > (ret[-1]['end'] - ret[-1]['start']):
                    ret[-1] = separator
                continue

            ret.append(separator)

        return ret

    def _format_separators(self, separators: list) -> list:
        '''Formats the timecodes of the separators in the HH:MM:SS format'''
        ret = []

        for separator in separators:
            ret.append({
                'start': self.get_hhmmss(separator['start']),
                'end': self.get_hhmmss(separator['end']),
                'tag': separator['tag'],
            })

        return ret
