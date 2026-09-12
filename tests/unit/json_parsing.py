# Script created by opencode:e-research/arc:apex
# Prompt: unit tests for the json answer parsing of the base operator (_parse_dirty_json and _parse_trailing_json).

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

# import the base operator from the repository root, whatever the working directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from operators.base.operator import Operator


class _ConcreteOperator(Operator):
    '''The abstract base operator reduced to what the json parsing needs to run'''

    def _apply(self):
        return None


class ParseDirtyJsonTestCase(unittest.TestCase):
    '''_parse_dirty_json: plain, fenced, malformed and paragraph-then-json answers'''

    def setUp(self):
        self.operator = _ConcreteOperator()

    def test_plain_json_answers_are_parsed(self):
        self.assertEqual(self.operator._parse_dirty_json('{"a": 1}'), {'a': 1})
        self.assertEqual(self.operator._parse_dirty_json('[1, 2]'), [1, 2])

    def test_fenced_json_answers_are_parsed(self):
        self.assertEqual(self.operator._parse_dirty_json('```json\n{"a": 1}\n```'), {'a': 1})

    def test_fenced_json_with_text_around_is_parsed(self):
        self.assertEqual(self.operator._parse_dirty_json('prose ```json [1, 2] ``` trailing'), [1, 2])

    def test_surrounding_whitespace_is_ignored(self):
        self.assertEqual(self.operator._parse_dirty_json('  \n[1, 2] \n'), [1, 2])

    def test_malformed_json_stays_raw_and_warns(self):
        with redirect_stdout(io.StringIO()) as captured:
            ret = self.operator._parse_dirty_json('{"a": }')
        self.assertEqual(ret, '{"a": }')
        self.assertIn('Invalid JSON format', captured.getvalue())

    def test_prose_stays_raw_without_warning(self):
        with redirect_stdout(io.StringIO()) as captured:
            ret = self.operator._parse_dirty_json('plain prose, no json at all')
        self.assertEqual(ret, 'plain prose, no json at all')
        self.assertEqual(captured.getvalue(), '')

    def test_non_string_answers_are_returned_unchanged(self):
        for answer in [{'a': 1}, [1, 2], None, 42]:
            with self.subTest(answer=answer):
                self.assertEqual(self.operator._parse_dirty_json(answer), answer)

    def test_empty_string_is_returned_unchanged(self):
        self.assertEqual(self.operator._parse_dirty_json(''), '')

    def test_paragraphs_ending_with_an_array_are_parsed(self):
        answer = ('I analysed the excerpt carefully.\n\n'
                  'It contains a single separator between two distinct programmes.\n\n'
                  '[{"start": "00:12:34", "end": "00:12:41", "tag": "colour bars"}]')
        self.assertEqual(self.operator._parse_dirty_json(answer),
                         [{'start': '00:12:34', 'end': '00:12:41', 'tag': 'colour bars'}])

    def test_paragraphs_ending_with_an_object_are_parsed(self):
        answer = 'Here is my answer after watching the whole excerpt.\n\n{"separators": [{"start": 30, "end": 35, "tag": "static"}]}'
        self.assertEqual(self.operator._parse_dirty_json(answer),
                         {'separators': [{'start': 30, 'end': 35, 'tag': 'static'}]})

    def test_nested_trailing_object_is_returned_whole(self):
        self.assertEqual(self.operator._parse_dirty_json('Paragraph.\n{"a": [1, 2]}'), {'a': [1, 2]})

    def test_truncated_json_stays_raw(self):
        answer = 'prose then truncated {"a": 1'
        self.assertEqual(self.operator._parse_dirty_json(answer), answer)

    def test_trailing_bare_fence_is_tolerated(self):
        self.assertEqual(self.operator._parse_dirty_json('Some paragraphs.\n\n[{"start": 0, "end": 5}]\n```'),
                         [{'start': 0, 'end': 5}])

    def test_fully_bare_fenced_json_is_parsed(self):
        self.assertEqual(self.operator._parse_dirty_json('```\n[1, 2]\n```'), [1, 2])


class ParseTrailingJsonTestCase(unittest.TestCase):
    '''_parse_trailing_json: answers made of paragraphs ending with an array or an object'''

    def setUp(self):
        self.operator = _ConcreteOperator()

    def test_returns_none_for_plain_prose(self):
        self.assertIsNone(self.operator._parse_trailing_json('no structure in here'))

    def test_returns_none_for_empty_text(self):
        self.assertIsNone(self.operator._parse_trailing_json(''))

    def test_returns_none_when_brackets_are_followed_by_text(self):
        self.assertIsNone(self.operator._parse_trailing_json('Broadcast in [2001].'))

    def test_returns_the_array_ending_the_text(self):
        self.assertEqual(self.operator._parse_trailing_json('prose then the answer: [1, 2]'), [1, 2])

    def test_returns_the_object_ending_the_text(self):
        self.assertEqual(self.operator._parse_trailing_json('prose then the answer: {"a": 1}'), {'a': 1})

    def test_mid_text_brackets_are_rejected_in_favour_of_the_trailing_array(self):
        self.assertEqual(self.operator._parse_trailing_json('In [2001] we saw several idents.\n\nLater came the following: [1, 2]'), [1, 2])

    def test_bracketed_fragment_ending_the_text_is_parsed(self):
        # known tradeoff: a prose answer genuinely ending with a bracketed fragment parses as an array
        self.assertEqual(self.operator._parse_trailing_json('Broadcast in [2001]'), [2001])

    def test_trailing_fence_is_stripped_before_parsing(self):
        self.assertEqual(self.operator._parse_trailing_json('prose\n[1, 2]\n```'), [1, 2])


if __name__ == '__main__':
    unittest.main()
