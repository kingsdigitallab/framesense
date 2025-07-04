import torch 
from PIL import Image
from torch.utils.data import DataLoader
import numpy as np
import torchvision.transforms as transforms
import torchvision
from pathlib import Path
import sys
import json

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


response = {
    'error': '',
    'class': '',
}

# read the image file name from the first comamnd line argument
arguments = sys.argv
if len(arguments) > 0:
    image_file_name = arguments[1]

    detector = ScaleDetector()
    res = detector.classify(image_file_name)
    response = {
        'error': '',
        'class': res,
    }
else:
    response = {
        'error': 'input image not provided',
        'class': '',
    }

print(json.dumps(response, indent=2))

if response['error']:
    sys.exit(1)
