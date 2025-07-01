from ..base.operator import Operator
from pathlib import Path
from importlib import import_module
import inspect

class Operators(Operator):
    '''List all available operators'''

    def get_operators_info(self):
        ret = []

        all_operators_path = Path(__file__).parent.parent
        for operator_path in all_operators_path.iterdir():
            if not (operator_path / 'operator.py').is_file(): continue

            operator_module = import_module(f'..{operator_path.name}.operator', package=__package__)

            for name, obj in operator_module.__dict__.items():
                if not (isinstance(obj, type) and issubclass(obj, Operator)): continue
                if inspect.isabstract(obj): continue

                doc = (obj.__doc__ or '').split('\n')[0]

                # we have at least one concrete operator
                # print(f'{operator_path.name}: {doc}')
                ret.append({
                    'name': operator_path.name,
                    'doc': doc,
                })
                break

        ret = sorted(ret, key=lambda o: o['name'])

        return ret

    def apply(self, *args, **kwargs):
        ret = super().apply(*args, **kwargs)

        for op in self.get_operators_info():
            print(f'{op["name"]}: {op["doc"]}')

