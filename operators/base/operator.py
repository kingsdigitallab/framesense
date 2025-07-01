from abc import ABC, abstractmethod
import subprocess
import functools
from typing import Tuple
import inspect
from pathlib import Path
import sys
import os

ENGINES = ['docker', 'singularity']

class Operator(ABC):

    def set_context(self, context):
        self.context = context

    @abstractmethod
    def apply(self, *args, **kwargs):
        self._build_container_image()
        return None

    def _get_operator_folder_path(self) -> Path:
        # /home/u/src/prj/tools/framesense/operators/make_shots_scenedetect
        return Path(inspect.getfile(type(self))).parent

    def _get_container_image_name(self):
        '''returns "framesense/<operator_name>"'''
        operator_folder_path = self._get_operator_folder_path()
        return f'framesense/{operator_folder_path.name}'

    def _build_container_image(self):
        '''Builds a docker image from the operator's Dockerfile.
        Does nothing if Dockerfile not found.
        '''
        operator_folder_path = self._get_operator_folder_path()
        dockerfile_path = operator_folder_path / 'Dockerfile'
        if dockerfile_path.is_file():
            image_name = self._get_container_image_name()
            engine = self._detect_installed_container_engine()

            print(f'Update container image {image_name}')

            # TODO: adapt for Singularity
            self._run_command([
                engine,
                'build',
                '-t', image_name,
                '--progress', 'quiet',
                operator_folder_path
            ])

    def _run_in_operator_container(self, command_args: [str], binding: Tuple[Path, Path] = None, same_user=False):
        args = [self._get_container_image_name()] + command_args[:]
        self._run_in_container(args, binding, same_user)

    def _run_in_container(self, command_args: [str], binding: Tuple[Path, Path] = None, same_user=False):
        '''Runs a command in a new container.
        command_args: list of items
            the first item is the image name
            the second is the command to pass to the container
            the rest are arguments to the command
        '''
        engine = self._detect_installed_container_engine()
        if not engine:
            self._error('Container engine is not installed. Please install Docker or Singularity.')

        # command_args = [engine, 'run'] + command_args
        engine_command_args = [engine, 'run']

        # to ensure that all files are writable by the current user
        # but... not all images will like this
        if same_user:
            engine_command_args += ['--user', f'{os.getuid()}:{os.getgid()}']

        if binding:
            mounted_path = binding[0].absolute().resolve()

            command_args = [
                str(binding[1] / a.relative_to(mounted_path)) if isinstance(a, Path) else a
                for a in command_args
            ]
        
            flag = '-v'
            if engine == 'singularity':
                flag = '-b'
            if engine == 'docker':
                engine_command_args.append('--rm')

            engine_command_args += [flag, f'{mounted_path}:{binding[1]}']
        

        engine_command_args += command_args

        # print(engine_command_args)
        # subprocess.run(engine_command_args)
        self._run_command(engine_command_args)

    def _run_command(self, command_args: [str]):
        try:
            subprocess.run(command_args)
        except Exception as e:
            print(f'ERROR: Execution of the command has failed: {command_args}')
            raise e

    @functools.lru_cache()
    def _detect_installed_container_engine(self):
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

    def _sluggify(self, string):
        return re.sub(r'\W+', '-', str(string).lower()).strip('-')

    def _get_video_file_path(self, parent_folder_path: Path):
        video_extensions = [".mp4", ".mkv"]        
        
        parent_folder_path.stat
        videos = [
            p for p in parent_folder_path.glob("**/*") 
            if any(
                p.suffix.lower() == ext 
                for ext in video_extensions
            )
        ]
        
        return max(videos, key=lambda v: v.stat().st_size) if videos else None
    
    def _is_path_selected(self, path: Path):
        ret = True
        filter = self.context['command_args'].filter
        if filter:
            ret = filter.lower() in str(path).lower()
        return ret
