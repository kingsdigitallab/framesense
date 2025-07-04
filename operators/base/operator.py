from abc import ABC, abstractmethod
import subprocess
import functools
from typing import Tuple
import inspect
from pathlib import Path
import sys
import os
import json

ENGINES = ['docker', 'singularity']
# ENGINES = ['singularity', 'docker']

class Operator(ABC):

    def set_context(self, context):
        self.context = context

    def get_supported_arguments(self) -> dict[str, bool]:
        '''Returned dict specifies which framesense arguments 
        are supported (True) by this operator.'''
        return {
            'filter': False,
            'verbose': False,
            'redo': False,
            'dry_run': False,
        }

    def get_unsupported_arguments(self):
        ret = []
        for arg_name, is_supported in self.get_supported_arguments().items():
            if not is_supported and self._get_command_argument(arg_name):
                ret.append(arg_name)
        return ret

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

            print(f'Update {engine} image {image_name}')

            if engine == 'singularity':

                singularity_image_path = operator_folder_path / f'operator.sif'

                if not singularity_image_path.is_file() or (
                    singularity_image_path.stat().st_mtime < dockerfile_path.stat().st_mtime
                ):
                    if singularity_image_path.is_file():
                        singularity_image_path.unlink()

                    # first convert the Dockerfile to a Singularity.def
                    res = self._run_command([
                        'spython',
                        'recipe',
                        dockerfile_path,
                    ])
                    singularity_file_path = operator_folder_path / 'Singularity.def'
                    singularity_file_path.write_text(res.stdout)

                    # then build the image
                    # TODO: consider --remote instead of --fakeroot
                    res = self._run_command([
                        'singularity',
                        'build', 
                        '--fakeroot', 
                        singularity_image_path,
                        singularity_file_path
                    ])                

            if engine == 'docker':
                self._run_command([
                    engine,
                    'build',
                    '-t', image_name,
                    '--progress', 'quiet',
                    operator_folder_path
                ])

    def _run_in_operator_container(self, command_args: [str], binding: Tuple[Path, Path] = None, same_user=False):
        engine = self._detect_installed_container_engine()
        if engine == 'docker':
            args = [self._get_container_image_name()] + command_args[:]
        if engine == 'singularity':
            args = [str(self._get_operator_folder_path() / 'operator.sif')] + command_args[:]
        return self._run_in_container(args, binding, same_user)

    def _run_in_container(self, command_args: [str], binding: Tuple[Path, Path] = None, same_user=False):
        '''Runs a command in a new container.
        command_args: list of items
            the first item is the image name
            the second is the command to pass to the container
            the rest are arguments to the command
        '''
        engine = self._detect_installed_container_engine()

        # command_args = [engine, 'run'] + command_args
        engine_command_args = [engine]
        
        if engine == 'docker':
            engine_command_args.append('run')
        if engine == 'singularity':
            engine_command_args.append('exec')

        # to ensure that all files are writable by the current user
        # but... not all images will like this
        if same_user:
            if engine == 'docker':
                engine_command_args += ['--user', f'{os.getuid()}:{os.getgid()}']


        # bindings b/w host & container paths
        bindings = []

        # user-defined binding
        if binding:
            bindings.append(binding)

        # bind ./app to /app
        app_folder_path = self._get_operator_folder_path() / 'app'
        if app_folder_path.is_dir():
            bindings.append([
                app_folder_path,
                '/app'
            ])

        # user-defined binding
        for abinding in bindings: 
            mounted_path = abinding[0].absolute().resolve()

            command_args = [
                str(abinding[1] / a.relative_to(mounted_path)) if isinstance(a, Path) and a.is_relative_to(mounted_path) else a
                for a in command_args
            ]
        
            flag = '-v'
            if engine == 'singularity':
                flag = '-B'

            engine_command_args += [flag, f'{mounted_path}:{abinding[1]}']
        
        if engine == 'docker':
            engine_command_args.append('--rm')

        engine_command_args += command_args

        # print(engine_command_args)
        # subprocess.run(engine_command_args)
        return self._run_command(engine_command_args)

    def _run_command(self, command_args: [str]) -> subprocess.CompletedProcess[str]:
        res = None

        error_message = f'Execution of the command has failed: {command_args}'

        try:
            res = subprocess.run(command_args, capture_output=True, text=True)
            if res.returncode > 0:
                print('[START COMMAND ERROR--------------------')
                print(res.stderr)
                print('END COMMAND ERROR----------------------]')
                self._error(error_message)
        except Exception as e:
            print(f'ERROR: {error_message}')
            raise e
        
        return res

    @functools.lru_cache()
    def _detect_installed_container_engine(self, ignore_if_not_found=False):
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

        if not ret and not ignore_if_not_found:
            self._error(f'Container engine is not installed. Please install one of these applications: {', '.join(ENGINES)}.')

        return ret

    def _error(self, message):
        print(f'ERROR: {message}', file=sys.stderr)
        sys.exit(1)

    def _is_verbose(self):
        return bool(self._get_command_argument('verbose'))

    def _is_redo(self):
        return bool(self._get_command_argument('redo'))

    def _get_command_argument(self, arg_name, default=''):
        ret = getattr(self.context['command_args'], arg_name, default)
        return ret

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
        filter = self._get_command_argument('filter')
        if filter:
            ret = filter.lower() in str(path).lower()
        return ret

    def _read_data_file(self, data_file_path: Path):
        ret = {
            'meta': {
            },
            'data': [
            ]
        }

        if data_file_path.is_file():
            res = data_file_path.read_text()
            ret = json.loads(res)

        return ret

    def _write_data_file(self, data_file_path: Path, content: dict):
        data_file_path.write_text(json.dumps(content, indent=2))
