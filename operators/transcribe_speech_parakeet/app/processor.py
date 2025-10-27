import torch 
from pathlib import Path
import sys
import json
from flask import Flask, request, jsonify

PORT = 5000
# https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3
MODEL = "nvidia/parakeet-tdt-0.6b-v3"

'''
Usage:

1. Single transcription from command line:

`python processor.py /path/to/my/sound.wav`

2. Bulk transcription from a http service:

2.1 load the model and service

`python processor.py serve`

2.2 call the service

`curl localhost:5000/process?input_path=/path/to/my/sound.wav`

2.3 stop the service

`curl localhost:5000/stop`

In all cases responses are in json:

on success:

{
    "error": "",
    "result": [
        {
            "segment": "This is play acting, but in reality it's designed to shock.",
            "start_offset": 62,
            "end_offset": 116,
            "start": 4.96,
            "end": 9.28
        },
    ]
}

on failure:

{
    "error": "ERROR MESSAGE",
    "result": []
}

'''

class Transcriber: 
    '''...
    '''

    def __init__(self):
        import nemo.collections.asr as nemo_asr

        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'

        self.model = nemo_asr.models.ASRModel.from_pretrained(model_name=MODEL)
        # use local attention to avoid OOM errors on long-form audio
        self.model.change_attention_model(self_attention_model="rel_pos_local_attn", att_context_size=[256, 256])

    def transcribe(self, sound_path):
        ret = ''
        sound_path = Path(sound_path)

        output = self.model.transcribe([str(sound_path)], timestamps=True)
        
        segment_timestamps = output[0].timestamp['segment']

        return segment_timestamps


if __name__ == '__main__':
    response = {
        'error': 'input sound not provided',
        'result': [],
    }

    # read the sound file name from the first comamnd line argument
    arguments = sys.argv

    if len(arguments) > 1:
        first_arg = arguments[1]

        transcriber = Transcriber()

        if first_arg == 'serve':
            app = Flask(__name__)

            @app.route('/process', methods=['GET'])
            def transcribe():
                sound_path = request.args.get('input_path', None)

                if sound_path:
                    res = transcriber.transcribe(sound_path)
                    response = {
                        'error': '',
                        'result': res,
                    }
                else:
                    response = {
                        'error': 'input image not provided',
                        'result': [],
                    }
                
                return jsonify(response)

            @app.route('/stop', methods=['GET'])
            def stop():
                # yes... Flask does NOT have a shutdown function.
                import signal, os
                os.kill(os.getpid(), signal.SIGINT)

            app.run(debug=True, host='0.0.0.0', port=PORT)
        elif first_arg == 'load_model':
            response = {
                'error': '',
                'result': [],
            }
        else:
            sound_path = first_arg

            res = transcriber.transcribe(sound_path)
            response = {
                'error': '',
                'result': res,
            }

    print(json.dumps(response, indent=2))

    if response['error']:
        sys.exit(1)
