# Script created by opencode:e-research/arc:apex
# Prompt: unit tests for the percent-encoding of the input_path query parameter
# of the processing service requests (_make_service_process_url of the base operator).

import sys
import unittest
from urllib.parse import unquote
from pathlib import Path

# import the base operator from the repository root, whatever the working directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from operators.base.operator import Operator

URL_PREFIX = 'http://localhost:5000/process?input_path='


class _ConcreteOperator(Operator):
    '''The abstract base operator reduced to what the service url needs to run'''

    def _apply(self):
        return None


class MakeServiceProcessUrlTestCase(unittest.TestCase):
    '''_make_service_process_url: percent-encoding of the input_path'''

    def setUp(self):
        self.operator = _ConcreteOperator()

    def test_paths_with_spaces_and_brackets_are_percent_encoded(self):
        container_path = Path('/data/NWFA 58 [THE LAUNCHING OF FORMBY LIFEBOAT]/00.00.00-157-full/00.00.00-157-full.wav')

        url = self.operator._make_service_process_url(container_path)

        self.assertTrue(url.startswith(URL_PREFIX))
        self.assertNotIn(' ', url)
        self.assertNotIn('[', url)
        self.assertNotIn(']', url)
        self.assertIn('NWFA%2058%20%5BTHE%20LAUNCHING', url)

    def test_encoded_input_path_decodes_back_to_the_original_path(self):
        container_path = Path('/data/NWFA 58 [THE LAUNCHING OF FORMBY LIFEBOAT]/00.00.00-157-full.wav')

        url = self.operator._make_service_process_url(container_path)

        input_path = url[len(URL_PREFIX):]
        self.assertEqual(unquote(input_path), str(container_path))

    def test_slashes_stay_literal(self):
        url = self.operator._make_service_process_url(Path('/data/godfather/clip.mp4'))

        self.assertEqual(url, f'{URL_PREFIX}/data/godfather/clip.mp4')


if __name__ == '__main__':
    unittest.main()
