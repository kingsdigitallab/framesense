# Script created by opencode:e-research/arc:apex
# Prompt: unit tests for the FFMPEG filter escaping of the srt path in sub_clips_ffmpeg
# (_escape_filter_path), which deals with the paths whose video folder name contains characters
# special to the FFMPEG filter syntax, such as the brackets of a batch title like
# 'NWFA 57 [GOVERNMENT PROPAGANDA FILMS - THE WAR YEARS]'.

import sys
import unittest
from pathlib import Path

# import the operators from the repository root, whatever the working directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from operators.sub_clips_ffmpeg.operator import SubClipsFFMPEG

PARAMS = {
    'font_size': 24,
    'font': 'Sans',
    'bold': 1,
    'outline': 3,
    'shadow': 1,
    'text_color': '&H00FFFFFF',
    'outline_color': '&H00000000',
    'shadow_color': '&H00000000',
}
FORCE_STYLE = 'FontSize=24,FontName=Sans,Bold=1,Outline=3,Shadow=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H00000000'
BRACKETED_SRT_PATH = Path('/data/NWFA 57 [GOVERNMENT PROPAGANDA FILMS - THE WAR YEARS]/00.00.00-150-full/00.00.00-150-full.srt')
BRACKETED_SRT_ESCAPED = r"/data/NWFA 57 \[GOVERNMENT PROPAGANDA FILMS - THE WAR YEARS\]/00.00.00-150-full/00.00.00-150-full.srt"
ALL_SPECIALS_SRT_PATH = Path("/data/don't: a=b\\c[1]; e,f.srt")
ALL_SPECIALS_SRT_ESCAPED = r"/data/don\\\'t\\: a\\=b\\\\c\[1\]\; e\,f.srt"


class EscapeFilterPathTestCase(unittest.TestCase):
    '''_escape_filter_path: the characters special to the FFMPEG filter syntax are escaped, the others left as is'''

    def setUp(self):
        self.operator = SubClipsFFMPEG()
        self.operator.params = dict(PARAMS)

    def test_path_without_special_characters_is_left_unchanged(self):
        self.assertEqual(
            self.operator._escape_filter_path(Path('/data/video1/00.00.00-62-full/00.00.00-62-full.srt')),
            '/data/video1/00.00.00-62-full/00.00.00-62-full.srt',
        )

    def test_brackets_are_escaped(self):
        self.assertEqual(
            self.operator._escape_filter_path(BRACKETED_SRT_PATH),
            BRACKETED_SRT_ESCAPED,
        )

    def test_every_special_character_is_escaped_with_the_right_number_of_backslashes(self):
        # the filter value is unescaped twice by FFMPEG, so [ ] , ; need one backslash,
        # : = need two (one is consumed by each unescaping) and ' \ need three and four
        self.assertEqual(
            self.operator._escape_filter_path(ALL_SPECIALS_SRT_PATH),
            ALL_SPECIALS_SRT_ESCAPED,
        )


class GetSubtitlesFilterTestCase(unittest.TestCase):
    '''_get_subtitles_filter: the srt path is translated to its container equivalent, escaped, and completed with the styling options'''

    def setUp(self):
        self.operator = SubClipsFFMPEG()
        self.operator.params = dict(PARAMS)

    def test_filter_burns_the_srt_of_a_bracketed_video_folder(self):
        collection_path = Path('/cephfs/batches')
        srt_path = collection_path / 'NWFA 57 [GOVERNMENT PROPAGANDA FILMS - THE WAR YEARS]' / '00.00.00-150-full' / '00.00.00-150-full.srt'

        self.assertEqual(
            self.operator._get_subtitles_filter(srt_path, collection_path),
            f"subtitles={BRACKETED_SRT_ESCAPED}:force_style='{FORCE_STYLE}'",
        )


if __name__ == '__main__':
    unittest.main()
