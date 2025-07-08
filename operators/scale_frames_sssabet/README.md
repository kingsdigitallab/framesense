# scale_frames_sssabet

## Input

* frames (e.g. godfather/00.00.03-62/shots/001/0001.jpg)

## Output

* frames metadata file (e.g. godfather/00.00.03-62/shots/001/frames.json) 
with a `scale_sssabet` attribute under each item in the frames list.

`scale_sssabet` will take one of those values:
* ECS: Extreme close-up shot
* CS: close-up shot
* MS: medium shot
* FS: full shot
* LS: long shot

Examples of frames.json after running this operator.

```
{
  "meta": {},
  "data": [
    {
      "id": "0001",
      "attributes": {
        "scale_sssabet": "FS"
      }
    },
    {
      "id": "0003",
      "attributes": {
        "scale_sssabet": "FS"
      }
    },
    {
      "id": "0002",
      "attributes": {
        "scale_sssabet": "ECS"
      }
    }
  ]
}
```

The first entry in that frames list with `"id": "0001"` refers to frame image 0001.jpg in the same folder.

## Concepts

In film studies/industry the term is 'shot scale' or 'shot size'. 

Because the scale can vary within a single shot,
(e.g. zooming in from a extreme long shot to a full shot),
the operator works at the frame level,
and can yield different values for different frames
within the same shot.

This explains why we detect shot scale on individual frames,
which can sound confusing.

Also note that the full taxonomy of shot scales 
is wider than what this operator can detect
and the interpretation of a scale can be subjective.

## Method

Use a pretrained model //github.com/sssabet/Shot_Type_Classification 
to infer the shot scale from a frame image resized to 128x128 pixels.
The model is a pytorch convolutional neural network 
based on Mobilenet_v3 architecture.

The operator internally works as a client-server:
* `app/detect.py` is a python web server that runs within a container, 
loads the model, 
listens to requests on localhost:5000/detect?image_path=/path/to/my/image.jpg,
classify the image 
and returns it as a json structure
* `operator.py` is a python client that launches the server in a container,
sends a request for each frame image and write the output into frames.json

Applies to all frames in the collections.

## Parameters (-p)

Not supported

## Run if

The frame has no value for the attribute `scale_sssabet` in `frames.json`.

## Residue

Frames which are no longer included in the collections may remain in `frames.json`.

## Redo (-r)

Will rewrite the frame scale attributes `scale_sssabet` in the `frames.json` for all frames.

## Based on

The classifier code and model are borrowed from [Shot_Type_Classification](https://github.com/sssabet/Shot_Type_Classification), which were developped by [Saeed Shafiee Sabet](https://github.com/sssabet). 

That model was trained on MovieShots dataset ([paper with code](https://paperswithcode.com/dataset/movieshots), [arxiv](https://arxiv.org/abs/2008.03548)).

Architecture of the model is [Mobilenet_v3](https://huggingface.co/docs/timm/en/models/mobilenet-v3)
