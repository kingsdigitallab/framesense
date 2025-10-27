import torch 
from PIL import Image
from torch.utils.data import DataLoader
import numpy as np
import torchvision.transforms as transforms
import torchvision
from pathlib import Path
import sys
import json
from flask import Flask, request, jsonify

PORT = 5000

'''
Usage:

1. Single image detection from command line:

`python processor.py /path/to/my/image.jpg`

2. Bulk image detections from a http service:

2.1 load the model and service

`python processor.py serve`

2.2 call the service

`curl localhost:5000/process?input_path=/path/to/my/image.jpg`

2.3 stop the service

`curl localhost:5000/stop`

In all cases responses are in json:

on success:

{
    "error": "",
    "result": "MS"
}

on failure:

{
    "error": "ERROR MESSAGE",
    "result": ""
}

'''

class ScaleDetector: 
    '''Shot scale classification from frames based on //github.com/sssabet/Shot_Type_Classification
    
    The model and code are borrowed from the following repository
    //github.com/sssabet/Shot_Type_Classification
    created by Saeed Shafiee Sabet.
    '''

    def __init__(self):

        if torch.__version__ >= "2.6":
            torch.serialization.add_safe_globals([torchvision.models.mobilenetv3.MobileNetV3])

        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'

        self.model = torch.load(
            '/models/Pytorch_Classification_50ep.pt',
            map_location=torch.device(self.device),
            weights_only=False
        )

    def classify(self, image_path):
        '''Returns the shot scale classification of the image as a string:
        ECS, CS, MS, FS or LS
        '''
        ret = ''
        image_path = Path(image_path)
        frame = Image.open(image_path)

        IMAGE_SIZE = [128, 128]

        data_transformation = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Resize(IMAGE_SIZE),
                transforms.Normalize([0.485, 0.456, 0.406],[0.229, 0.224, 0.225])
            ]
        )
        images = data_transformation(frame)

        with torch.no_grad():
            n_correct=0
            n_samples=0
            #images=images.to(device)
            pred = self.model(images.view([1, 3, 128, 128]).to(self.device))
            _, res = torch.max(pred,1)
            

        if res.item()==0:
            p='CS'
        elif res.item()==1:
            p='ECS'
        elif res.item()==2:
            p='FS'
        elif res.item()==3:
            p='LS'
        else:
            p='MS'

        # if p!=1:
        #     print(f'The Model predicts that it is a {p}')

        return p


if __name__ == '__main__':
    response = {
        'error': 'input image not provided',
        'result': '',
    }

    # read the image file name from the first comamnd line argument
    arguments = sys.argv

    if len(arguments) > 0:
        first_arg = arguments[1]

        detector = ScaleDetector()

        if first_arg == 'serve':
            app = Flask(__name__)

            @app.route('/process', methods=['GET'])
            def process():
                image_path = request.args.get('input_path', None)

                if image_path:
                    res = detector.classify(image_path)
                    response = {
                        'error': '',
                        'result': res,
                    }
                else:
                    response = {
                        'error': 'input image not provided',
                        'result': '',
                    }
                
                return jsonify(response)

            @app.route('/stop', methods=['GET'])
            def stop():
                # yes... Flask does NOT have a shutdown function.
                import signal, os
                os.kill(os.getpid(), signal.SIGINT)

            app.run(debug=True, host='0.0.0.0', port=PORT)
        else:    
            image_path = first_arg

            res = detector.classify(image_path)
            response = {
                'error': '',
                'result': res,
            }

    print(json.dumps(response, indent=2))

    if response['error']:
        sys.exit(1)
