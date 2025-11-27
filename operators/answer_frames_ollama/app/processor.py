# import torch 
from pathlib import Path
import sys
import json
import datetime
# from flask import Flask, request, jsonify

# PORT = 5000
# https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3
# MODEL = 'gemma3:1b'

# CONTEXT_LENGTH = 32000

PARAMS = json.loads(Path('/app/params.json').read_text())

'''
Usage:

TODO

on failure:

{
    "error": "ERROR MESSAGE",
    "result": []
}

'''


if __name__ == '__main__':
    response = {
        'error': 'input image not provided',
        'result': [],
    }

    arguments = sys.argv

    if len(arguments) > 1:
        first_arg = arguments[1]

        from ollama import ChatResponse
        from ollama import Client

        client = Client(
            host=PARAMS['ollama_host']
        )

        client.pull(PARAMS['model'])

        response: ChatResponse = client.chat(
            model=PARAMS['model'], 
            messages=[
                {
                    'role': 'user',
                    'content': PARAMS['prompt'],
                    'images': [first_arg],
                },
            ], options={
                'num_ctx': PARAMS['context_length'],
                'seed': PARAMS['seed'],
            }
        )

        response = {
            'error': '',
            'result': response.message.content,
        }

        print(json.dumps(response))

    if response['error']:
        sys.exit(1)
