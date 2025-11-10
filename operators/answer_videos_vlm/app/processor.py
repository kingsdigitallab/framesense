import traceback
import torch 
from pathlib import Path
import sys
import json
from flask import Flask, request, jsonify
from transformers import Qwen3VLForConditionalGeneration, Qwen3VLMoeForConditionalGeneration, AutoProcessor
import signal
import os
# from qwen_vl_utils import process_vision_info
from datetime import datetime

PARAMS = json.loads(Path('/app/params.json').read_text())

torch.manual_seed(int(PARAMS['seed']))

PORT = 5000

MODEL = PARAMS['model']

MODEL_FOR_GENERATION = Qwen3VLForConditionalGeneration
if '-A' in MODEL:
    MODEL_FOR_GENERATION = Qwen3VLMoeForConditionalGeneration

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
    free, total = torch.cuda.mem_get_info()
    used = total - free
    return used / 1024**3

def show_vram():
    print(f"* VRAM used: {get_vram():.2f} GB")

def format_time(delta):
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"    

class VQA: 
    '''...
    '''

    def __init__(self):
        import subprocess

        # Not a good idea to do it here, too late probably
        # Also it should be installed in the docker image
        # 
        # print('Installing')
        # res = subprocess.run(["bash", "install-attention.bash"])
        # if res.returncode != 0:
        #     exit(3)
        # print('Load model')

        self.model = MODEL_FOR_GENERATION.from_pretrained(
            MODEL,
            dtype=torch.bfloat16,
            # dtype="auto",
            attn_implementation="flash_attention_2",
            #attn_implementation="sdpa",
            device_map="auto",
        )

        print('Create processor')
        
        self.processor = AutoProcessor.from_pretrained(MODEL)

        # device_name = torch.cuda.get_device_name(torch.cuda.current_device())


    def answer(self, video_path):
        video_path = Path(video_path)

        # we need to read it again
        PARAMS = json.loads(Path('/app/params.json').read_text())
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "video",
                        "video": str(video_path.absolute()),
                    },
                    {"type": "text", "text": PARAMS['prompt']},
                ],
            }
        ]

        inputs = self.processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt"
        )
        inputs = inputs.to(self.model.device)

        # Inference: Generation of the output
        generated_ids = self.model.generate(
            **inputs,
            max_new_tokens=int(PARAMS['max_new_tokens']),
            temperature=0.7,
            top_k=20,
            top_p=0.8,
            #seed=3407,
        )
        # generated_ids = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS)
        generated_ids_trimmed = [
            out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        output_text = self.processor.batch_decode(
            generated_ids_trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False
        )

        return output_text[0]


if __name__ == '__main__':
    response = {
        'error': 'input video not provided',
        'result': [],
    }

    # read the sound file name from the first comamnd line argument
    arguments = sys.argv

    if len(arguments) > 1:
        first_arg = arguments[1]

        answerer = VQA()

        if first_arg == 'serve':
            app = Flask(__name__)

            @app.route('/process', methods=['GET'])
            def transcribe():
                try:
                    video_path = request.args.get('input_path', None)

                    if video_path:
                        vram_before = get_vram()
                        t0 = datetime.now()
                        res = answerer.answer(video_path)
                        t1 = datetime.now()
                        response = {
                            'error': '',
                            'result': res,
                            'stats': {
                                'vram_before': vram_before,
                                'vram_after': get_vram(),
                                'duration': format_time(t1 - t0),
                            }
                        }
                    else:
                        response = {
                            'error': 'input image not provided',
                            'result': [],
                        }
                except Exception as e:
                    error_message = str(e)
                    stack_trace = traceback.format_exc()
                    # Return or use both as needed
                    error_path = Path('/app/error.log')
                    log_message = f'''Message: {error_message}\nStack Trace:\n{stack_trace}'''
                    error_path.write_text(log_message)
                    raise e

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
            video_path = first_arg

            res = answerer.answer(video_path)
            response = {
                'error': '',
                'result': res,

            }

    print(json.dumps(response, indent=2))

    if response['error']:
        sys.exit(1)
