from pathlib import Path
from ..base.operator import Operator

# quality of mp3 output from 0 (poorest) to 9 (best)
SOUND_QUALITY_DEFAULT = 4

class ExtractSoundFFMPEG(Operator):
    '''Extract sound from clips using FFMPEG'''

    def get_supported_arguments(self):
        ret = super().get_supported_arguments()
        ret['redo'] = True
        ret['filter'] = True
        ret['skip'] = True
        return ret

    def _apply(self):
        ret = None

        stats = {
            'created': 0,
            'existing': 0,
            'skipped': 0,
        }

        for col in self.context['collections']:
            for video_folder_path in sorted(col['attributes']['path'].iterdir()):
                if video_folder_path.is_dir():
                    for clip_folder_path in sorted(video_folder_path.iterdir()):
                        if clip_folder_path.is_dir():
                            clip_path = self._get_video_file_path(clip_folder_path)
                            if clip_path:
                                outcome = self._extract_sound(clip_path)
                                if outcome:
                                    stats[outcome] += 1

        self._log(f"sound files created: {stats['created']}; already existing: {stats['existing']}; clips skipped: {stats['skipped']}")

        return ret

    def _extract_sound(self, clip_path: Path):
        ret = None

        if not self._is_path_selected(clip_path):
            return ret

        sound_path = clip_path.with_suffix('.wav')

        if self._is_redo() or not sound_path.exists():
            self._log(sound_path)
            video_folder_path = clip_path.parent.parent
            command = [
                "ffmpeg",
                "-i", clip_path,
                # "-vn", 
                # "-acodec", "libmp3lame", # mp3
                # "-acodec", "pcm_s16le", # wav
                "-ar", str(self.get_param('audio_rate')), # sample rate
                # "-ac", "2", #  nb of audio channels
                # "-q:a", str(SOUND_QUALITY_DEFAULT),
                ## "-map", "0:a:0", # maps the first audio stream from the input file
                "-ac", "1",
                "-y", # overwrite output
                sound_path
            ]
            res = self._run_in_operator_container(command, [video_folder_path, '/data'], same_user=True, skip=self._is_skip())

            if res.returncode > 0:
                sound_path.unlink(missing_ok=True)
                self._warn(f'Sound not extracted from clip: {clip_path}')
                ret = 'skipped'
            else:
                ret = 'created'
        else:
            ret = 'existing'

        return ret
