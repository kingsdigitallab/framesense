from abc import ABC, abstractmethod
import subprocess
import functools
from typing import Tuple
import inspect
from pathlib import Path
import sys
import os
import json
import urllib.request
import time
import re
import http
from datetime import datetime

ENGINES = ['docker', 'singularity']
SERVICE_PORT = 5000


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
            'parameters': False,
        }

    def get_unsupported_arguments(self):
        ret = []
        for arg_name, is_supported in self.get_supported_arguments().items():
            if not is_supported and self._get_framesense_argument(arg_name):
                ret.append(arg_name)
        return ret

    def apply(self):
        self._before_apply()
        ret = self._apply()
        self._after_apply()
        return ret

    def _before_apply(self):
        self.stop_service()
        self._build_container_image()

    @abstractmethod
    def _apply(self):
        return None

    def _after_apply(self):
        self.stop_service()

    def _get_operator_folder_path(self) -> Path:
        # /home/u/src/prj/tools/framesense/operators/make_shots_scenedetect
        return Path(inspect.getfile(type(self))).parent

    def _get_operator_name(self) -> str:
        return self._get_operator_folder_path().name
    
    def _get_container_image_name(self):
        ret = None
        
        operator_name = self._get_operator_folder_path().name

        engine = self._detect_installed_container_engine()

        if engine == 'docker':
            ret = f'framesense/{operator_name}'

        if engine == 'singularity':
            ret = self._get_singularity_folder_path() / f'{operator_name}.sif'

        return ret

    def _get_container_name(self, suffix=''):
        operator_folder_path = self._get_operator_folder_path()
        ret =  f'framesense_{operator_folder_path.name}'
        if suffix:
            ret += '_' + suffix
        return ret

    def _build_container_image(self):
        '''Builds a docker image from the operator's Dockerfile.
        Does nothing if Dockerfile not found.
        '''
        operator_folder_path = self._get_operator_folder_path()
        dockerfile_path = operator_folder_path / 'Dockerfile'
        if dockerfile_path.is_file():

            engine = self._detect_installed_container_engine()

            image_name = self._get_container_image_name()

            self._log(f'Update {engine} image {image_name}')

            if engine == 'singularity':

                # singularity_image_path = operator_folder_path / f'operator.sif'
                singularity_image_path = image_name

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

                    # see gh-12
                    singularity_definition_content = self._convert_singularity_definition(
                        res.stdout, 
                        dockerfile_path.parent
                    )

                    singularity_definition_path = Path(f'{str(image_name).rstrip(".sif")}.def')
                    singularity_definition_path.write_text(singularity_definition_content)

                    # then build the image

                    # This works without logging into a remote endpoint
                    # But requires privileged access, not met on HPC infrastructure.
                    # For presonal machine.
                    singularity_build_method = '--fakeroot'
                    if self._is_logged_into_singularity_remote():
                        singularity_build_method = '--remote'

                    res = self._run_command([
                        'singularity',
                        'build',
                        singularity_build_method, 
                        singularity_image_path,
                        singularity_definition_path
                    ])                

            if engine == 'docker':
                self._run_command([
                    engine,
                    'build',
                    '-t', image_name,
                    '--progress', 'quiet',
                    operator_folder_path
                ])

    def _is_logged_into_singularity_remote(self):
        ret = False

        res = self._run_command(['singularity', 'remote', 'status'])

        if "logged in as" in res.stdout.lower():
            ret = True

        return ret

    def _start_service_in_operator_container(self, command_args: [str], binding: Tuple[Path, Path] = None, same_user=False, port_mapping=None, wait_for_message=''):
        if self.service:
            # we can't reuse it b/c the bindings could be different
            self.stop_service()

        self._log(f'Waiting for service in container...')
        self.service = self._run_in_operator_container(command_args, binding, same_user=same_user, port_mapping=port_mapping, is_service=True)
        
        os.set_blocking(self.service.stdout.fileno(), False)  # Now readline() will be non-blocking
        os.set_blocking(self.service.stderr.fileno(), False)  # Now readline() will be non-blocking
        
        # TODO: set a timeout
        # start = time.time()
        self.service_output = ''
        i = 0
        while True:
            # this is blocking call (NOT, see above)
            line = self.service.stdout.readline()
            # todo: wait for port instead
            if line:
                i += 1
                self.service_output += line
                # self._debug(line)
                if wait_for_message in line:
                    # needed when we stop & start again to avoid operator fetching to fail
                    time.sleep(1)
                    break
            else:
                time.sleep(0.5)
                # self._debug(self.service.returncode)
                if self.service.poll() is not None:
                    # service terminated
                    error_lines = ''
                    for l in self.service.stderr.readline():
                        if l is None:
                            break
                        error_lines += l
                    info = self.service_output
                    if error_lines:
                        info = error_lines
                    self._error(f'Service launch failed ({self.service.returncode}): {info}')

    def _is_service_running(self):
        ret = False

        res = None

        engine = self._detect_installed_container_engine()
        if engine == 'docker':
            res = self._run_command([engine, 'ps'])
        if engine == 'singularity':
            service_name = self._get_container_name('service')
            res = self._run_command([engine, 'instance', 'list', service_name])
        
        if res:
            ret = self._get_container_name('service') in res.stdout

        return ret
    
    def stop_service(self):
        if self._is_service_running():
            service_name = self._get_container_name('service')

            self._log(f'Stopping service {service_name}...')

            engine = self._detect_installed_container_engine()

            if engine == 'docker':
                command_args = [
                    engine,
                    'stop',
                    service_name
                ]

            if engine == 'singularity':
                command_args = [
                    engine,
                    'instance',
                    'stop',
                    service_name
                ]

            res = self._run_command(command_args)
            # print(res)

        self.service = None
        self.service_output = ''
        self.service_collection_path = None
    
    def _call_service_processor(self, input_file_path: Path, collection_path: Path):
        ret = ''

        # current_time = datetime.now()
        # iso_string = current_time.strftime("%Y-%m-%d-%M-%S-%f")

        binding = [
            collection_path, 
            '/data'
        ]

        command_args = [
            'python',
            'processor.py',
            'serve'
        ]

        if self.service_collection_path != str(collection_path):
            # Do NOT use same_user for parakeet b/c host user can vary
            # Docker build could create dynamically, but not needed
            self._start_service_in_operator_container(command_args, binding, same_user=False, port_mapping=[SERVICE_PORT, SERVICE_PORT], wait_for_message='Serving Flask app')
            self.service_collection_path = str(collection_path)

        # send request to localhost:5000/process?input_path=frame_file_path

        # command_args = [
        #     'python',
        #     'processor.py',
        #     frame_file_path
        # ]

        # res = self._run_in_operator_container(command_args, binding, same_user=True)

        # response = json.loads(res.stdout)

        input_file_path_in_container = binding[1] / input_file_path.relative_to(binding[0])
        
        self._log(input_file_path.relative_to(binding[0]))
        response = self._fetch_json(f'http://localhost:{SERVICE_PORT}/process?input_path={input_file_path_in_container}')

        error = response.get('error', '')
        if not error:
            ret = response.get('result', '')
            # print(ret)
        else:
            self._error(f'Processing service returned error. Input = {input_file_path}; Error = {error}.')

        return ret

    def _run_in_operator_container(self, command_args: [str], binding: Tuple[Path, Path] = None, same_user=False, port_mapping=None, is_service=False):
        return self._run_in_container(self._get_container_image_name(), command_args, binding, same_user, port_mapping, is_service)

    def _run_in_container(self, container_image_name, command_args: [str], binding: Tuple[Path, Path] = None, same_user=False, port_mapping=None, is_service=False):
        '''Runs a command in a new container.
        command_args: list of items
            NO (the first item is the image name)
            the second is the command to pass to the container
            the rest are arguments to the command
        
        TODO: rewrite, it has gradually become hard to understand; many scenarios are covered
        TODO: clearer to completely separate singularity from docker? two different sub-functions?
        TODO: pass the image name in a separate argument, rather than at the beginning of command_args
        '''
        engine = self._detect_installed_container_engine()

        command_args = command_args[:]

        engine_command_args = [engine]
        
        if engine == 'docker':
            engine_command_args.append('run')
        if engine == 'singularity':
            if is_service:
                engine_command_args += ['instance', 'start']
            else:
                engine_command_args.append('exec')

        # to ensure that all files are writable by the current user
        # but... not all images will like this (1000 may not exist there)
        # and the current user on host is not always 1000
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

            if engine == 'singularity' and not is_service:
                engine_command_args += [
                    '--pwd',
                    '/app'
                ]

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

            if port_mapping:
                engine_command_args += ['-p', f'{port_mapping[0]}:{port_mapping[1]}']
                # TODO: port mapping for singularity?
            
        if engine == 'docker':
            if self.does_docker_support_gpu():
                engine_command_args += ['--gpus', 'all']

        if engine == 'singularity':
            # TODO: test
            engine_command_args += ['--nv']

        service_name = self._get_container_name('service')

        if is_service:
            if engine in ['docker']:
                engine_command_args += ['--name', service_name]
            
        engine_command_args.append(container_image_name)

        if is_service and engine in ['singularity']:
            # after the image name
            engine_command_args.append(service_name)

            # we need two separate calls to singularity:
            # one to start the container as an instance
            # e.g. singularity instance start -B /home/X/src/prj/tools/framesense/tests/collections/hollywood:/data -B /home/jeff/src/prj/tools/framesense/operators/scale_frames_sssabet/app:/app /home/X/src/prj/tools/framesense/singulary/scale_frames_sssabet.sif framesense_scale_frames_sssabet_service
            self._run_command(engine_command_args)

            # a second to launch the service within the instance
            # e.g. singularity exec --pwd /app instance://framesense_scale_frames_sssabet_service python server.py server

            service_args = []
            if app_folder_path.is_dir():
                service_args = ['--pwd', '/app']

            return self._run_service([
                'singularity',
                'exec'] + service_args + [                
                f'instance://{service_name}',
            ] + command_args)
        else:
            engine_command_args += command_args        

            if is_service:
                return self._run_service(engine_command_args)
            else:
                return self._run_command(engine_command_args)

    
    def _run_command(self, command_args: [str]) -> subprocess.CompletedProcess[str]:
        res = None

        command_as_string = ' '.join([str(a) for a in command_args])

        self._debug(f'running command {command_as_string}')

        error_message = f'Execution of the command has failed: {command_as_string}'

        try:
            # cwd is needed for singularity build from .def (with relative path in COPY)
            res = subprocess.run(command_args, capture_output=True, text=True, cwd=self._get_operator_folder_path())
            if res.returncode > 0:
                self._log('[START COMMAND ERROR--------------------')
                self._log(res.stderr)
                self._log('END COMMAND ERROR----------------------]')
                self._error(error_message)
        except Exception as e:
            self._log(f'{error_message}', 'ERROR')
            raise e
        
        return res

    def _run_service(self, command_args: [str]):
        # TODO: remove code duplication with _run_command
        ret = None

        command_as_string = ' '.join([str(a) for a in command_args])

        self._debug(f'running command {command_as_string}')

        error_message = f'Execution of the command has failed: {command_args}'

        try:
            # TODO: error managment
            ret = subprocess.Popen(
                command_args, 
                cwd=self._get_operator_folder_path(), 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
        except Exception as e:
            self._log(f'{error_message}', 'ERROR')
            raise e
        
        return ret

    @functools.lru_cache()
    def _detect_installed_container_engine(self, ignore_if_not_found=False):
        ret = os.getenv('FRAMESENSE_CONTAINER_ENGINE', None)

        if ret is not None:
            return ret

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
            self._error(f'Container engine is not installed. Please install one of these applications: {", ".join(ENGINES)}.')
        
        return ret

    def _get_singularity_folder_path(self) -> Path:
        ret = self._get_framesense_folder_path() / 'singulary'
        if not ret.exists():
            ret.mkdir()
        return ret
    
    def _get_framesense_folder_path(self) -> Path:
        return self.context['framesense_folder_path']
    
    def _error(self, message):
        self._log(message, status='ERROR')

    def _debug(self, message):
        if self._is_debug():
            self._log(message, status='DEBUG')

    def _log(self, message, status='INFO'):
        now = datetime.now()
        print(
            f'{now.hour}:{now.minute}:{now.second}.{int(now.microsecond / 10e5)} [{status:<5}] [{self._get_operator_name()}] {message}', 
            file=sys.stderr if status == 'ERROR' else sys.stdout
        )
        if status == 'ERROR':
            sys.exit(1)

    def _is_verbose(self):
        return bool(self._get_framesense_argument('verbose'))

    def _is_redo(self):
        return bool(self._get_framesense_argument('redo'))

    def _get_framesense_argument(self, arg_name, default=''):
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
        filter = self._get_framesense_argument('filter')
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

    def _get_operator_parameters(self):
        return self._get_framesense_argument('parameters')

    def _fetch_json(self, url):
        try:
            res = urllib.request.urlopen(url)
        except urllib.error.URLError as e:
            self._error(f'error while fetching {url}, {str(e.reason)}')
        except http.client.RemoteDisconnected as e:
            self._error(f'error while fetching {url}, {str(e)}')

        content = res.read().decode('utf-8')
        return json.loads(content)

    def _is_debug(self):
        ret = self.context.get('debug', False)
        return ret

    def _convert_singularity_definition(self, definition: str, base_path: Path) -> str:
        lines = []

        # See gh-12, we convert the source paths under %files to absolute paths
        #
        # COPY app/requirements.txt /models/requirements.txt
        #
        # app/requirements.txt is relative to the Dockerfile in Docker.
        # But in singularity we need to convert it to absolute paths
        # to build it without error with a remote container engine.
        # With --fakeroot build, the paths are relative to the current dir.
        # With --remote, relative paths don't work (unless file in the current dir)
        #
        # %file app/requirement.txt /molels/requirements.txt
        #
        # =>
        #
        # %file /absolute/path/to/app/requirement.txt /models/requirements.txt
        #
        def make_path_absolute(match):
            # e.g. app/requirements.txt
            ret = Path(match.group(1))

            if not ret.is_absolute():
                ret = base_path / ret

            return str(ret)

        section = ''
        for line in definition.split('\n'):
            if line.strip().startswith('%'):
                section = line.strip()[1:]
            else:
                if section == 'files':
                    line = re.sub(r'^(?:\s*)(\S+)', make_path_absolute, line)
            
            lines.append(line)

        ret = '\n'.join(lines)

        return ret

    def does_docker_support_gpu(self):
        ret = False
        cuda_visible_devices = os.environ.get("CUDA_VISIBLE_DEVICES", None)
        if cuda_visible_devices != '':
            command_args = ['docker', 'run', '--rm', '--gpus', 'all', 'alpine']
            res = subprocess.run(command_args, capture_output=True, text=True, cwd=self._get_operator_folder_path())
            ret = res.returncode == 0

        return ret
