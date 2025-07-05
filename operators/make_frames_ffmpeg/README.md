# make_frames_ffmpeg

## Input

* shots (shots/XXX/shot.mp4)

## Output

* frames (shots/XXX/0001.jpg, etc.)

## Method

Use ffmpeg to extract frames
from a shot (shot.mp4)
and save the frames in the same folder
with a frame number starting from 0001. 

If no parameters (-p) are provided,
the first, middle and last frame are extracted.

Applies to all shots in the collections.

## Parameters (-p)

If a parameter is provided to FrameSense (-p)
it will be mapped to ffmpeg -vf argument
to control the sampling of frames.

For instance:
* `-p 'select=not(mod(n\,10))'` will extract every 10th frame
* `-p 'fps=2'` will extract two frames per second

## Run if

No *.jpg already exists under the shots/XXX folder.

## Redo (-r)

Supported.

This will first delete all existing /shots/XXX/*.jpg 
and /shots/XXX/frames.json

## Filtering (-f)

Supported

