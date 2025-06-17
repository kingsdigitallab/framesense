from abc import ABC, abstractmethod
import subprocess
import functools
from typing import Tuple
from pathlib import Path
import sys

ENGINES = ['docker', 'singularity']

class Operator(ABC):

    def set_context(self, context):
        self.context = context

    @abstractmethod
    def apply(self, *args, **kwargs):
        return None

    def _run_in_container(self, command_args: [str], binding: Tuple[Path, Path] = None):
        engine = self._get_installed_container_engine()
        if not engine:
            self._error('Container engine is not installed. Please install Docker or Singularity.')

        mounted_path = binding[0].absolute().resolve()

        command_args = [
            str(binding[1] / a.relative_to(mounted_path)) if isinstance(a, Path) else a
            for a in command_args
        ]
        
        # command_args = [engine, 'run'] + command_args
        engine_command_args = [engine, 'run']
        if binding:
            flag = '-v'
            if engine == 'singularity':
                flag = '-b'
            engine_command_args += [flag, f'{mounted_path}:{binding[1]}']

        engine_command_args += command_args

        print(engine_command_args)
        subprocess.run(engine_command_args)

    @functools.lru_cache()
    def _get_installed_container_engine(self):
        ret = None
        for engine in ENGINES:
            try:
                output = subprocess.check_output([engine, '--version'])
                ret = engine
                break
            except subprocess.CalledProcessError:
                pass
            except FileNotFoundError:
                pass
        return ret

    def _error(self, message):
        print(f'ERROR: {message}', file=sys.stderr)
        sys.exit(1)

    def _is_verbose(self):
        return self.context['command_args'].verbose