# make_shots_scenedetect

## Input

* clips (VIDEO/CLIP.mp4)

## Output

* shots (VIDEO/shots/XXX/001/shot.mp4, etc.)
* shots table (VIDEO/shots/shots.csv)

## Method

Use [PySceneDetect](https://www.scenedetect.com/cli/)
to extract shots from a clip (e.g. VIDEO/CLIP.mp4)
and save the shots under VIDEO/shots/001/shot.mp4,
VIDEO/shots/002/shot.mp4, etc.
PySceneDetect also saves the shots metadata table under VIDEO/shots/shots.csv.

If no parameters (-p) are provided,
the `detect-adaptive` detection method is used.

Applies to all clips in the collections.

## Parameters (-p)

If a parameter is provided to FrameSense (-p)
it will be used to specify the detection method
and its control parameters.

For instance:
* `-p 'detect-threshold -t 23'` to use the threshold method with a given threshold of 23
* `-p 'detect-content'` to use the content method

For more information see [PySceneDetect documentation about the various methods](https://www.scenedetect.com/docs/latest/cli.html#detectors`)

## Run if

No VIDEO/shots already exists.

## Redo (-r)

Supported.

If first delete the content of VIDEO/shots.

## Filtering (-f)

Supported

