# Script created by opencode:e-research/arc:apex
# Prompt: unit tests for the -f filter and -e exclude selection of the base operator (_is_path_selected).

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

# import the base operator from the repository root, whatever the working directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from operators.base.operator import Operator


class _ConcreteOperator(Operator):
    '''The abstract base operator reduced to what the path selection needs to run'''

    def _apply(self):
        return None


class _FilteringOperator(_ConcreteOperator):
    '''A concrete operator supporting the -f filter and -e exclude arguments'''

    def get_supported_arguments(self):
        ret = super().get_supported_arguments()
        ret['filter'] = True
        return ret


class IsPathSelectedTestCase(unittest.TestCase):
    '''_is_path_selected: keyword filtering, keyword exclusion and their combination'''

    def setUp(self):
        self.operator = _ConcreteOperator()

    def _is_selected(self, path, filter='', exclude=''):
        self.operator.set_context({
            'collections': [],
            'collections_meta': {},
            'command_args': SimpleNamespace(filter=filter, exclude=exclude),
        })
        return self.operator._is_path_selected(Path(path))

    def test_all_paths_are_selected_without_arguments(self):
        self.assertTrue(self._is_selected('/data/godfather/00.00.03-62/clip.mp4'))

    def test_filter_selects_paths_containing_a_keyword(self):
        self.assertTrue(self._is_selected('/data/godfather/00.00.03-62/clip.mp4', filter='godfather'))
        self.assertFalse(self._is_selected('/data/godfather/00.00.03-62/clip.mp4', filter='matrix'))

    def test_filter_accepts_several_pipe_separated_keywords(self):
        self.assertTrue(self._is_selected('/data/godfather/00.00.03-62/clip.mp4', filter='matrix|godfather'))
        self.assertFalse(self._is_selected('/data/godfather/00.00.03-62/clip.mp4', filter='matrix|avatar'))

    def test_filter_is_case_insensitive_and_trims_spaces(self):
        self.assertTrue(self._is_selected('/data/GodFather/clip.mp4', filter=' godfather '))
        self.assertTrue(self._is_selected('/data/godfather/clip.mp4', filter='GODFATHER'))

    def test_empty_filter_keywords_are_ignored(self):
        self.assertTrue(self._is_selected('/data/godfather/clip.mp4', filter='|godfather|'))

    def test_filter_of_only_empty_keywords_selects_nothing(self):
        # pre-existing behaviour: any() over an empty keyword list is False
        self.assertFalse(self._is_selected('/data/godfather/clip.mp4', filter='| |'))

    def test_exclude_rejects_paths_containing_a_keyword(self):
        self.assertFalse(self._is_selected('/data/godfather/promo/clip.mp4', exclude='promo'))
        self.assertTrue(self._is_selected('/data/godfather/clips/clip.mp4', exclude='promo'))

    def test_exclude_accepts_several_pipe_separated_keywords(self):
        self.assertFalse(self._is_selected('/data/godfather/promo/clip.mp4', exclude='ads|promo'))
        self.assertTrue(self._is_selected('/data/godfather/promo/clip.mp4', exclude='ads|trailer'))

    def test_exclude_is_case_insensitive_and_trims_spaces(self):
        self.assertFalse(self._is_selected('/data/godfather/PROMO/clip.mp4', exclude=' promo '))

    def test_empty_exclude_keywords_are_ignored(self):
        self.assertTrue(self._is_selected('/data/godfather/promo/clip.mp4', exclude='| |'))

    def test_exclude_wins_over_filter(self):
        self.assertFalse(self._is_selected('/data/godfather/promo/clip.mp4', filter='godfather', exclude='promo'))

    def test_exclude_applies_without_filter(self):
        self.assertFalse(self._is_selected('/data/godfather/promo/clip.mp4', exclude='promo'))

    def test_path_matching_filter_and_not_excluded_is_selected(self):
        self.assertTrue(self._is_selected('/data/godfather/clips/clip.mp4', filter='godfather', exclude='promo'))


class UnsupportedArgumentsTestCase(unittest.TestCase):
    '''get_unsupported_arguments: the filter support flag governs both -f and -e'''

    def setUp(self):
        self.plain_operator = _ConcreteOperator()
        self.filtering_operator = _FilteringOperator()

    def _unsupported(self, operator, filter, exclude):
        operator.set_context({
            'collections': [],
            'collections_meta': {},
            'command_args': SimpleNamespace(filter=filter, exclude=exclude),
        })
        return operator.get_unsupported_arguments()

    def test_nothing_is_reported_without_arguments(self):
        self.assertEqual(self._unsupported(self.plain_operator, '', ''), [])

    def test_filter_and_exclude_are_unsupported_without_filter_support(self):
        self.assertEqual(self._unsupported(self.plain_operator, 'x', 'y'), ['filter', 'exclude'])

    def test_filter_alone_is_reported_when_only_f_is_used(self):
        self.assertEqual(self._unsupported(self.plain_operator, 'x', ''), ['filter'])

    def test_exclude_alone_is_reported_when_only_e_is_used(self):
        self.assertEqual(self._unsupported(self.plain_operator, '', 'y'), ['exclude'])

    def test_filter_support_covers_both_arguments(self):
        self.assertEqual(self._unsupported(self.filtering_operator, 'x', 'y'), [])


if __name__ == '__main__':
    unittest.main()
