import argparse
from pathlib import Path
from dotenv import load_dotenv
import os
import sys
import json
from importlib import import_module
import inspect

load_dotenv()

class CollectionToolkit:
    def __init__(self):
        pass

    def process_command_line(self):
        actions = {}
        epilog = 'Action:\n'

        actions = self._get_actions_info()
        for name, info in actions.items():
            epilog += f'  {name}:\n    {info['doc']}\n'

        parser = argparse.ArgumentParser(
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=epilog,
            description='Create and maintain a copy of a site.'
        )
        
        parser.add_argument("action", help="action to perform", choices=actions.keys())
        # parser.add_argument("-o", "--operator", help="operator to apply")
        parser.add_argument("-u", "--url", help="root url of site to copy")
        parser.add_argument("-v", "--verbose", action='store_true', help="enable verbose output")

        args = parser.parse_args()
        self.args = args

        self._read_collections_file()
        self.run_action(args.action)

        # actions[args.action]['function'](args)
        
        print(f'done ({args.action})')

    def run_action(self, operator_name):
        operator = self._get_operator(operator_name)
        context = self._get_context()
        operator.set_context(context)
        operator.apply()

    def _get_actions_info(self):
        ret = {}
        # yes... you read that right!
        from operators.operators.operator import Operators
        op = Operators()

        for operator_info in op.get_operators_info():
            ret[operator_info['name']] = operator_info

        return ret


    # def _get_actions_info(self):
    #     ret = {}
    #     for member_name in dir(self):
    #         if member_name.startswith('action_'):
    #             action_name = member_name[7:]
    #             method = getattr(self, member_name)
    #             ret[action_name] = {
    #                 'function': method,
    #                 'description': (method.__doc__ or '').split('\n')[0],
    #             }        
    #     return ret
    
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
        return {
            "collections": self.collections['data'],
            'collections_path': self.collections_path,
            "command_args": self.args,
        }

    def _is_verbose(self):
        return self.args.verbose

    def _read_collections_file(self):
        '''read collection file'''
        # get the path to the collections.json from env var "COLKIT_COLLECTIONS_PATH"
        collections_path = os.getenv('COLKIT_COLLECTIONS', None)
        if collections_path is None or not Path(collections_path).exists():
            self._error('COLKIT_COLLECTIONS environment variable should contain the path to a collections.json.')        
        
        self.collections_path = Path(collections_path).absolute().resolve()
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

colkit = CollectionToolkit()
colkit.process_command_line()
