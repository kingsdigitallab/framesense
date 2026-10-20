# Script created by opencode:e-research/arc:apex
# Prompt: unit tests for the transcribe_vad_parakeet operator (assignment of the transcribed segments to the voice
# segment containing their middle, clamping, offsets, dropping of the hallucinated segments landing into the
# inserted silences) and for its _transcribe flow (missing inputs, empty segments short-circuit, service errors).

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

# import the operator from the repository root, whatever the working directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from operators.transcribe_vad_parakeet.operator import TranscribeVADParakeet

CLIP_NAME = '00.00.03-62'

# the layout of a compacted sound made of the voice segments 4.96-9.28 and 53.1-58.7,
# separated by a 0.25 s silence, as returned by the app processor
LAYOUT = [
    {'original_start': 4.96, 'original_end': 9.28, 'compact_start': 0.0, 'compact_end': 4.32},
    {'original_start': 53.1, 'original_end': 58.7, 'compact_start': 4.57, 'compact_end': 10.17},
]

class _ConcreteOperator(TranscribeVADParakeet):
    '''The operator reduced to what the remap and _transcribe tests need to run'''

    def _apply(self):
        return None


class GetChunkOfSegmentTestCase(unittest.TestCase):
    '''_get_chunk_of_segment: assignment of a transcribed segment to a voice segment'''

    def setUp(self):
        self.operator = _ConcreteOperator()
        self.operator.params = {}

    def test_segment_fully_in_first_chunk_is_assigned_to_it(self):
        segment = {'start': 1.0, 'end': 2.0}

        self.assertEqual(self.operator._get_chunk_of_segment(segment, LAYOUT), LAYOUT[0])

    def test_segment_straddling_two_chunks_is_assigned_to_the_one_of_its_middle(self):
        segment = {'start': 3.0, 'end': 6.14}

        self.assertEqual(self.operator._get_chunk_of_segment(segment, LAYOUT), LAYOUT[1])

    def test_segment_in_the_silence_between_chunks_is_assigned_to_none(self):
        segment = {'start': 4.33, 'end': 4.55}

        self.assertIsNone(self.operator._get_chunk_of_segment(segment, LAYOUT))


class RemapResultTestCase(unittest.TestCase):
    '''_remap_result: segments mapped back into the timecodes of the clip sound'''

    def setUp(self):
        self.operator = _ConcreteOperator()
        self.operator.params = {}
        self.segments = [
            {'segment': 'Hello, Doctor.', 'start': 0.5, 'end': 2.0},
            {'segment': 'hallucinated', 'start': 4.33, 'end': 4.55},
            {'segment': 'Bye.', 'start': 5.0, 'end': 8.0},
        ]

    def test_segments_timecodes_are_mapped_into_the_voice_segments(self):
        result = self.operator._remap_result(self.segments, LAYOUT)

        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result[0]['start'], 5.46)
        self.assertAlmostEqual(result[0]['end'], 6.96)
        self.assertAlmostEqual(result[1]['start'], 53.1 + 5.0 - 4.57)
        self.assertAlmostEqual(result[1]['end'], 53.1 + 8.0 - 4.57)

    def test_segment_starting_in_the_silence_is_clamped_to_the_voice_segment_start(self):
        segment = {'segment': 'Bye.', 'start': 4.3, 'end': 5.3}

        result = self.operator._remap_result([segment], LAYOUT)

        self.assertAlmostEqual(result[0]['start'], 53.1)
        self.assertAlmostEqual(result[0]['end'], 53.1 + 5.3 - 4.57)

    def test_segment_ending_after_the_voice_segment_is_clamped_to_its_end(self):
        segment = {'segment': 'Bye.', 'start': 8.0, 'end': 11.0}

        result = self.operator._remap_result([segment], LAYOUT)

        self.assertAlmostEqual(result[0]['end'], 58.7)

    def test_hallucinated_segment_is_dropped(self):
        result = self.operator._remap_result(self.segments, LAYOUT)

        self.assertEqual([item['segment'] for item in result], ['Hello, Doctor.', 'Bye.'])

    def test_offsets_index_the_segments_joined_by_a_single_space(self):
        result = self.operator._remap_result(self.segments, LAYOUT)

        self.assertEqual(result[0]['start_offset'], 0)
        self.assertEqual(result[0]['end_offset'], 14)
        self.assertEqual(result[1]['start_offset'], 15)
        self.assertEqual(result[1]['end_offset'], 19)

    def test_empty_segments_give_an_empty_result(self):
        self.assertEqual(self.operator._remap_result([], LAYOUT), [])

    def test_empty_layout_gives_an_empty_result(self):
        self.assertEqual(self.operator._remap_result(self.segments, []), [])


class TranscribeTestCase(unittest.TestCase):
    '''_transcribe: the whole flow, from the inputs of the clip to transcription.json'''

    def setUp(self):
        self.tmp_folder = TemporaryDirectory()
        self.addCleanup(self.tmp_folder.cleanup)

        self.collection_path = Path(self.tmp_folder.name) / 'hollywood'
        self.clip_folder_path = self.collection_path / CLIP_NAME
        self.clip_folder_path.mkdir(parents=True)
        self.clip_path = self.clip_folder_path / f'{CLIP_NAME}.mp4'
        self.clip_path.touch()
        self.sound_path = self.clip_folder_path / f'{CLIP_NAME}.wav'
        self.transcription_path = self.clip_folder_path / 'transcription.json'
        self.voice_segments_path = self.clip_folder_path / 'voice_segments.json'

        self.operator = _ConcreteOperator()
        self.operator.context = {
            'collections': [{'attributes': {'path': self.collection_path}}],
            'collections_meta': {},
            'command_args': SimpleNamespace(),
        }
        self.operator.params = {}
        self.service_calls = []

    def _make_sound_file(self):
        self.sound_path.touch()

    def _make_voice_segments(self, segments):
        self.voice_segments_path.write_text(json.dumps(segments, indent=2))

    def _set_service_response(self, response):
        def _fake_call_service_processor(sound_path, collection_path, skip=False):
            self.service_calls.append(sound_path)
            return response

        self.operator._call_service_processor = _fake_call_service_processor

    def test_missing_sound_is_reported_missing(self):
        self._set_service_response({'error': '', 'result': [], 'layout': []})

        outcome = self.operator._transcribe(self.clip_path, self.collection_path)

        self.assertEqual(outcome, 'missing')
        self.assertFalse(self.transcription_path.exists())
        self.assertEqual(self.service_calls, [])

    def test_missing_voice_segments_are_reported_missing(self):
        self._make_sound_file()
        self._set_service_response({'error': '', 'result': [], 'layout': []})

        outcome = self.operator._transcribe(self.clip_path, self.collection_path)

        self.assertEqual(outcome, 'missing')
        self.assertFalse(self.transcription_path.exists())
        self.assertEqual(self.service_calls, [])

    def test_existing_transcription_is_left_untouched(self):
        self._make_sound_file()
        self._make_voice_segments([{'start': 4.96, 'end': 9.28}])
        self.transcription_path.write_text('[]')
        self._set_service_response({'error': '', 'result': [], 'layout': []})

        outcome = self.operator._transcribe(self.clip_path, self.collection_path)

        self.assertEqual(outcome, 'existing')
        self.assertEqual(self.service_calls, [])

    def test_redo_transcribes_the_clip_again(self):
        self._make_sound_file()
        self._make_voice_segments([{'start': 4.96, 'end': 9.28}])
        self.transcription_path.write_text('[]')
        self.operator.context['command_args'] = SimpleNamespace(redo=True)
        self._set_service_response({'error': '', 'result': [], 'layout': LAYOUT})

        outcome = self.operator._transcribe(self.clip_path, self.collection_path)

        self.assertEqual(outcome, 'created')
        self.assertEqual(self.service_calls, [self.sound_path])

    def test_empty_voice_segments_create_an_empty_transcription_without_calling_the_service(self):
        self._make_sound_file()
        self._make_voice_segments([])
        self._set_service_response({'error': '', 'result': [], 'layout': []})

        outcome = self.operator._transcribe(self.clip_path, self.collection_path)

        self.assertEqual(outcome, 'created')
        self.assertEqual(self.transcription_path.read_text(), '[]')
        self.assertEqual(self.service_calls, [])

    def test_service_error_skips_the_clip(self):
        self._make_sound_file()
        self._make_voice_segments([{'start': 4.96, 'end': 9.28}])
        self._set_service_response({'error': 'service crashed', 'result': [], 'layout': []})

        outcome = self.operator._transcribe(self.clip_path, self.collection_path)

        self.assertEqual(outcome, 'skipped')
        self.assertFalse(self.transcription_path.exists())
        self.assertEqual(self.service_calls, [self.sound_path])

    def test_response_without_layout_skips_the_clip(self):
        self._make_sound_file()
        self._make_voice_segments([{'start': 4.96, 'end': 9.28}])
        self._set_service_response({'error': '', 'result': [{'segment': 'Hi.', 'start': 0.0, 'end': 1.0}]})

        outcome = self.operator._transcribe(self.clip_path, self.collection_path)

        self.assertEqual(outcome, 'skipped')
        self.assertFalse(self.transcription_path.exists())

    def test_service_result_is_remapped_into_transcription_json(self):
        self._make_sound_file()
        self._make_voice_segments([{'start': 4.96, 'end': 9.28}, {'start': 53.1, 'end': 58.7}])
        response = {
            'error': '',
            'result': [
                {'segment': 'Hello, Doctor.', 'start': 0.5, 'end': 2.0, 'start_offset': 2, 'end_offset': 11},
                {'segment': 'hallucinated', 'start': 4.33, 'end': 4.55, 'start_offset': 12, 'end_offset': 13},
                {'segment': 'Bye.', 'start': 5.0, 'end': 8.0, 'start_offset': 20, 'end_offset': 40},
            ],
            'layout': LAYOUT,
        }
        self._set_service_response(response)

        outcome = self.operator._transcribe(self.clip_path, self.collection_path)

        self.assertEqual(outcome, 'created')
        result = json.loads(self.transcription_path.read_text())
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['segment'], 'Hello, Doctor.')
        self.assertAlmostEqual(result[0]['start'], 5.46)
        self.assertAlmostEqual(result[0]['end'], 6.96)
        self.assertEqual(result[0]['start_offset'], 0)
        self.assertEqual(result[0]['end_offset'], 14)
        self.assertEqual(result[1]['segment'], 'Bye.')
        self.assertAlmostEqual(result[1]['start'], 53.1 + 5.0 - 4.57)
        self.assertAlmostEqual(result[1]['end'], 53.1 + 8.0 - 4.57)
        self.assertEqual(result[1]['start_offset'], 15)
        self.assertEqual(result[1]['end_offset'], 19)


if __name__ == '__main__':
    unittest.main()
