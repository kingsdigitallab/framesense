import traceback
import torch 
from pathlib import Path
import sys
import json
from flask import Flask, request, jsonify
from transformers import AutoModel
import signal
import os
import re
# from qwen_vl_utils import process_vision_info
from datetime import datetime

PARAMS = json.loads(Path('/app/params.json').read_text())

torch.manual_seed(int(PARAMS['seed']))

PORT = 5000

MODEL = PARAMS['model']

SUPPORTED_MODELS = [
    "jinaai/jina-embeddings-v4", 
    "jinaai/jina-clip-v2"
]

if MODEL not in SUPPORTED_MODELS:
    res = {
        "result": "",
        "error": f"Unsupported model '{MODEL}'. Please use one of {SUPPORTED_MODELS}.",
    }
    print(json.dumps(res, indent=2))
    sys.exit(1)

OFFLOAD_FOLDER = "/hf_cache/offload"
Path(OFFLOAD_FOLDER).mkdir(parents=True, exist_ok=True)

'''
Usage:

TODO

on failure:

{
    "error": "ERROR MESSAGE",
    "result": []
}

'''

def get_vram():
    free, total = [0, 0]
    if torch.cuda.is_available():
        free, total = torch.cuda.mem_get_info()
    used = total - free
    return used / 1024**3

def show_vram():
    print(f"* VRAM used: {get_vram():.2f} GB")

def format_time(delta):
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"    

class Processor: 
    '''...
    '''

    def __init__(self):
        # https://huggingface.co/jinaai/jina-embeddings-v4
        # TODO: flash-attention
        options = {
        }

        if 'jina-embeddings-v4' in MODEL:
            options['attn_implementation'] = "flash_attention_2"

        model = AutoModel.from_pretrained(
            MODEL, 
            trust_remote_code=True, 
            # dtype=torch.float16,
            # attn_implementation="flash_attention_2",
            # attn_implementation="sdpa",
            device_map="auto",
            offload_folder=OFFLOAD_FOLDER,
            **options,
        )

        self.model = model

    def process(self, input):
        # we need to read it again
        # PARAMS = json.loads(Path('/app/params.json').read_text())
        ret = None

        is_image = False
        is_image = re.search(r'\.(jpg|png)$', input)

        if is_image:
            if 'jina-clip-v2' in MODEL:
                ret = self.model.encode_image(
                    images=[input]
                )        
            if 'jina-embeddings-v4' in MODEL:
                ret = self.model.encode_image(
                    images=[input],
                    task="retrieval",
                )        
        else:
            if 'jina-clip-v2' in MODEL:
                # https://huggingface.co/jinaai/jina-clip-v2
                ret = self.model.encode_text(
                    texts=input,
                    task="retrieval.query",
                )
            if 'jina-embeddings-v4' in MODEL:
                ret = self.model.encode_text(
                    texts=[input],
                    task="retrieval",
                    prompt_name="query",
                )

        return ret[0].tolist()

if __name__ == '__main__':
    response = {
        'error': 'input not provided',
        'result': [],
    }

    # read the sound file name from the first comamnd line argument
    arguments = sys.argv

    if len(arguments) > 1:
        first_arg = arguments[1]

        processor = Processor()
        
        if first_arg == 'serve':

            app = Flask(__name__)

            @app.route('/process', methods=['GET'])
            def process():
                try:
                    input = request.args.get('input_path', None)

                    if input:
                        vram_before = get_vram()
                        t0 = datetime.now()
                        res = processor.process(input)
                        t1 = datetime.now()
                        response = {
                            'error': '',
                            # TODO: emcoding?
                            'result': res,
                            'stats': {
                                'vram_before': vram_before,
                                'vram_after': get_vram(),
                                'duration': format_time(t1 - t0),
                            }
                        }
                    else:
                        response = {
                            'error': 'input not provided',
                            'result': [],
                        }

                except Exception as e:
                    error_message = str(e)
                    stack_trace = traceback.format_exc()
                    # Return or use both as needed
                    error_path = Path('/app/error.log')
                    log_message = f'''Message: {error_message}\nStack Trace:\n{stack_trace}'''
                    error_path.write_text(log_message)
                    response = {
                        'error': f'{type(e)}: {error_message}',
                        'result': [],
                        'stack': stack_trace
                    }

                return jsonify(response)

            @app.route('/stop', methods=['GET'])
            def stop():
                # yes... Flask does NOT have a shutdown function.
                os.kill(os.getpid(), signal.SIGINT)

            app.run(debug=True, host='0.0.0.0', port=PORT)

        elif first_arg == 'load_model':
            response = {
                'error': '',
                'result': [],
            }
        else:
            input = first_arg

            res = processor.process(input)
            response = {
                'error': '',
                'result': res,
            }

    print(json.dumps(response, indent=2))

    if response['error']:
        sys.exit(1)
