import argparse
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
import os
import sys
import json
from importlib import import_module
import inspect
import time

dotenv_path = os.getenv('FRAMESENSE_DOTENV_PATH', None)

if dotenv_path:
    if not Path(dotenv_path).is_file():
        print(f'ERROR: custom .env file not found in specified path ({dotenv_path}) by FRAMESENSE_DOTENV_PATH')
        exit(1)
else:
    dotenv_path = find_dotenv()

if dotenv_path:
    dotenv_path = Path(dotenv_path).absolute().resolve()
    load_dotenv(dotenv_path=dotenv_path)

class FrameSense:
    def __init__(self):
        pass

    def process_command_line(self):
        t0 = time.time()

        actions = {}
        epilog = 'Action:\n'

        actions = self._get_actions_info()
        for name, info in actions.items():
            epilog += f'  {name}:\n    {info["doc"]}\n'

        parser = argparse.ArgumentParser(
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=epilog,
            description='Apply an operator to a video collection'
        )
        
        parser.add_argument("operator", help="operator to apply", choices=actions.keys())
        # parser.add_argument("-o", "--operator", help="operator to apply")
        parser.add_argument("-f", "--filter", help="filter paths", default='')
        parser.add_argument("-v", "--verbose", action='store_true', help="enable verbose output")
        parser.add_argument("-r", "--redo", action='store_true', help="redo")
        parser.add_argument("-n", "--dry-run", action='store_true', help="perform a trial run with no changes made")
        parser.add_argument("-p", "--parameters", help="parameters to pass to the operator")
        parser.add_argument("-s", "--serve", help="run an operator as a service over a collection", metavar='COLLECTION')
       
        args = parser.parse_args()
        self.args = args

        self._read_collections_file()
        self.run_action(args.operator)

        # actions[args.action]['function'](args)

        duration = time.time() - t0

        print(f'done ({args.operator}, in {int(duration)} s.)')

    def run_action(self, operator_name):
        operator = self._get_operator(operator_name)
        context = self._get_context()
        operator.set_context(context)
        unsupported_args = operator.get_unsupported_arguments()
        if unsupported_args:
            self._error(f'The operator "{operator_name}" does not support these arguments: {", ".join(list(unsupported_args))}')

        operator.apply()

    def _get_actions_info(self):
        ret = {}
        # yes... you read that right!
        from operators.operators.operator import Operators
        op = Operators()

        for operator_info in op.get_operators_info():
            ret[operator_info['name']] = operator_info

        return ret

    def _get_operator(self, operator_name):
        ret = None

        from operators.base.operator import Operator
        operator_module_path = f'operators.{operator_name}.operator'

        try:
            operator_module = import_module(operator_module_path)
        except ModuleNotFoundError:
            self._error(f'Operator not found: {operator_module_path}')

        for name, obj in operator_module.__dict__.items():
            operator_class = None
            if isinstance(obj, type) and issubclass(obj, Operator):
                operator_class = obj
        if operator_class:
            if inspect.isabstract(operator_class):
                self._error(f'No concrete operator found in {operator_module_path}')
            ret = operator_class()

        return ret

    def _get_context(self):
        ret = {
            "framesense_folder_path": Path(__file__).parent.resolve(),
            "collections": self.collections['data'],
            "collections_meta": self.collections.get('meta', {}),
            'collections_path': self.collections_path,
            "command_args": self.args,
            'debug': self._is_debug()
        }
        return ret

    def _is_debug(self):
        is_debug = os.getenv('FRAMESENSE_DEBUG', False)
        return str(is_debug).lower() in ['1', 'true', 'yes', 'on']

    def _is_verbose(self):
        if self.args.verbose:
            return 1
        return 0

    def _read_collections_file(self):
        '''read collection file'''

        global dotenv_path

        # get the path to the collections.json from env var "FRAMESENSE_COLLECTIONS_PATH"
        collections_path = os.getenv('FRAMESENSE_COLLECTIONS', None)
        
        if collections_path is None:
            self._error(f'FRAMESENSE_COLLECTIONS environment variable not found.')
        
        collections_path = Path(collections_path)

        if not collections_path.is_absolute():
            if dotenv_path:
                collections_path = dotenv_path.parent / collections_path
            
        collections_path = collections_path.absolute().resolve()

        if not Path(collections_path).is_file():
            self._error(f'FRAMESENSE_COLLECTIONS environment variable should contain a valid path to a collections.json ({collections_path}).')
        
        self.collections_path = collections_path

        self.collections = json.loads(self.collections_path.read_text())

        # convert all the relative paths in collections to absolute Path objects
        for col in self.collections['data']:
            for key in ['path', 'annotations_path']:
                path = col['attributes'].get(key, None)
                if not path: continue
                path = Path(path)
                if not path.is_absolute():
                    path = (self.collections_path.parent / path)
                path = path.resolve()
                col['attributes'][key] = path

    def _error(self, message):
        # log the message to stderr and exit
        print(f'ERROR: {message}', file=sys.stderr)
        sys.exit(1)

framesense = FrameSense()
framesense.process_command_line()

