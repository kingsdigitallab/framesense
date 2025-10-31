# import torch 
from pathlib import Path
import sys
import json
# from flask import Flask, request, jsonify

PORT = 5000
# https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3
MODEL = 'gemma3:4b'

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

def get_hhmmss(seconds):
    hours = int(seconds // 3600)
    seconds %= 3600
    minutes = int(seconds // 60)
    seconds %= 60
    return f"{hours:02d}:{minutes:02d}:{int(seconds):02d}"

if __name__ == '__main__':
    response = {
        'error': 'input sound not provided',
        'result': [],
    }

    # read the sound file name from the first comamnd line argument
    arguments = sys.argv

    if len(arguments) > 1:
        first_arg = arguments[1]

        # transcriber = Transcriber()

        if first_arg == 'serve':
            pass
        else:
            from ollama import chat
            from ollama import ChatResponse

            transcription = json.loads(Path(first_arg).read_text())
            transcription_srt = '\n'.join([
                f'{get_hhmmss(item["start"])} {item["segment"]}'
                for item in transcription
            ])

            prompt = f'''
QUESTION:
Return a JSON Array with all the place names mentioned in the video transcription that follows.
On each line of the transcription, there is a time stamp (HH:MM:SS) followed by a sentence spoken in the video at that time.
For each place name in the returned array include the following:

* `start`: the timestamp at which the place was mentioned
* `locality`: the city, town or village the the place belongs to
* `place`: the place name

`locality` and `place` together should allow to uniquely pinpoint the place on a map.

TRANSCRIPTION:

```
{transcription_srt}
```

YOUR ANSWER:
            '''
            
            response: ChatResponse = chat(model=MODEL, messages=[
                {
                    'role': 'user',
                    'content': prompt,
                },
            ], options={
                'num_ctx': 32000
            })

            sound_path = first_arg

            response = {
                'error': '',
                'result': response.message.content,
            }

    print(json.dumps(response, indent=2))

    if response['error']:
        sys.exit(1)
