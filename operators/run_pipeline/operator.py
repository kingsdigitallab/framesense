from ..base.operator import Operator
from importlib import import_module
import inspect
import time

DEFAULT_PIPELINE_NAME = 'default'

class RunPipeline(Operator):
    '''Run a series of operators defined in a pipeline of the collections file'''

    def get_supported_arguments(self):
        ret = super().get_supported_arguments()
        ret['filter'] = True
        ret['verbose'] = True
        return ret

    def _apply(self):
        ret = None

        pipeline_name = self.get_param('pipeline', DEFAULT_PIPELINE_NAME)
        pipelines = self.context['collections_meta'].get('pipelines', {})

        if pipeline_name not in pipelines:
            available = ', '.join(pipelines.keys()) if pipelines else 'none'
            self._error(f'No pipeline named "{pipeline_name}" in the collections file. Available pipelines: {available}')

        operations = pipelines[pipeline_name].get('operations', [])

        if not isinstance(operations, list):
            self._error(f'The operations of pipeline "{pipeline_name}" should be an array.')

        self._log(f'Running pipeline "{pipeline_name}" ({len(operations)} operations)')

        prepared_operations = self._prepare_operations(operations, pipeline_name)

        for i, operation_run in enumerate(prepared_operations):
            self._run_operation(operation_run, i + 1, len(prepared_operations))

        return ret

    def _prepare_operations(self, operations, pipeline_name):
        '''Validates all the operations before running any of them, then returns the operator instances and contexts to run'''
        ret = []

        for i, operation in enumerate(operations):
            position = f'operation #{i + 1} of pipeline "{pipeline_name}"'

            if not isinstance(operation, dict):
                self._error(f'The {position} should be an object.')

            operator_name = operation.get('operator', None)
            if not operator_name or not isinstance(operator_name, str):
                self._error(f'The {position} is missing its operator property.')

            if operator_name == self._get_operator_name():
                self._error(f'Pipelines cannot run other pipelines (the {position} uses {operator_name}).')

            operation_params = operation.get('params', {})
            if not isinstance(operation_params, dict):
                self._error(f'The params of the {position} should be an object.')

            operator = self._get_operator_instance(operator_name)

            self._check_operation_params(operation_params, operator_name, operator)

            ret.append({
                'operator_name': operator_name,
                'operator': operator,
                'context': self._make_operation_context(operation_params, operator_name),
            })

        return ret

    def _check_operation_params(self, operation_params, operator_name, operator):
        params_path = operator._get_operator_folder_path() / 'params.json'
        supported_param_names = set(self.read_json(params_path).keys()) if params_path.exists() else set()

        unsupported_param_names = [k for k in operation_params.keys() if k not in supported_param_names]

        if unsupported_param_names:
            supported = ', '.join(sorted(supported_param_names)) if supported_param_names else 'none'
            self._error(f'Parameter `{unsupported_param_names[0]}` is not supported by operator {operator_name}. Supported parameters: {supported}')

    def _make_operation_context(self, operation_params, operator_name):
        '''Returns a context where the params of the operation supersede the collections-level params; the environment variables are applied by the operator itself afterwards'''
        collections_meta = dict(self.context['collections_meta'])
        meta_params = dict(collections_meta.get('params', {}))
        operator_params = dict(meta_params.get(operator_name, {}))
        operator_params.update(operation_params)
        meta_params[operator_name] = operator_params
        collections_meta['params'] = meta_params

        ret = dict(self.context, collections_meta=collections_meta)
        return ret

    def _get_operator_instance(self, operator_name):
        ret = None

        operator_module_path = f'operators.{operator_name}.operator'
        try:
            operator_module = import_module(operator_module_path)
        except ModuleNotFoundError:
            self._error(f'Operator not found: {operator_name}')

        for name, obj in operator_module.__dict__.items():
            if not (isinstance(obj, type) and issubclass(obj, Operator)): continue
            if inspect.isabstract(obj): continue
            ret = obj()
            break

        if ret is None:
            self._error(f'No concrete operator found in {operator_module_path}')

        return ret

    def _run_operation(self, operation_run, position, total):
        operator = operation_run['operator']
        operator_name = operation_run['operator_name']

        operator.set_context(operation_run['context'])

        if not operator.get_supported_arguments().get('filter', False) and self._get_framesense_argument('filter'):
            self._warn(f'Operator {operator_name} does not support the -f filter argument; the operation will process all its inputs.')

        self._log(f'[{position}/{total}] running {operator_name}...')

        t0 = time.time()
        operator.apply()
        duration = time.time() - t0

        self._log(f'[{position}/{total}] {operator_name} done (in {int(duration)} s.)')
