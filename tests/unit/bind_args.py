# Script created by opencode:e-research/arc:apex
# Prompt: unit tests for the container bind arguments of the base operator (_get_bind_args),
# in particular the singularity --mount flag used for the paths containing commas.

import sys
import unittest
from pathlib import Path

# import the base operator from the repository root, whatever the working directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from operators.base.operator import Operator

COMMA_PATH = '/data/NWFA 473 [WATERFALL MILL, BLACKBURN]'
QUOTED_MOUNT_SOURCE = 'src=/data/NWFA 473 [WATERFALL MILL, BLACKBURN]'


class _ConcreteOperator(Operator):
    '''The abstract base operator reduced to what the bind args need to run'''

    def _apply(self):
        return None


class GetBindArgsTestCase(unittest.TestCase):
    '''_get_bind_args: -v for docker and -B for singularity, --mount for the singularity paths with a comma'''

    def setUp(self):
        self.operator = _ConcreteOperator()

    def test_docker_uses_v_regardless_of_commas(self):
        self.assertEqual(
            self.operator._get_bind_args('docker', Path('/data/my,dir'), '/data'),
            ['-v', '/data/my,dir:/data'],
        )

    def test_singularity_uses_b_for_comma_free_paths(self):
        self.assertEqual(
            self.operator._get_bind_args('singularity', Path('/data/nwfa 143 whit-sunday procession'), '/data'),
            ['-B', '/data/nwfa 143 whit-sunday procession:/data'],
        )

    def test_singularity_uses_a_csv_quoted_mount_for_paths_with_a_comma(self):
        self.assertEqual(
            self.operator._get_bind_args('singularity', Path(COMMA_PATH), '/data'),
            ['--mount', f'type=bind,"{QUOTED_MOUNT_SOURCE}",dst=/data'],
        )

    def test_singularity_doubles_the_quotes_of_the_mounted_path(self):
        self.assertEqual(
            self.operator._get_bind_args('singularity', Path('/data/my"dir,name'), '/data'),
            ['--mount', 'type=bind,"src=/data/my""dir,name",dst=/data'],
        )


if __name__ == '__main__':
    unittest.main()
