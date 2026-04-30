# make_shots_scenedetect

## Input

* clips (e.g. `gotdfather/00.00.03-62/00.00.03-62.mp4`)

## Output

* shots (e.g. `gotdfather/00.00.03-62/shots/001/shot.mp4`)
* shots table (e.g. `gotdfather/00.00.03-62/shots/shots.csv`)

## Method

Use [PySceneDetect](https://www.scenedetect.com/cli/)
to extract shots from a clip 
(e.g. `gotdfather/00.00.03-62/00.00.03-62.mp4`)
and save the shots under 
`gotdfather/00.00.03-62/shots/001/shot.mp4`,
`gotdfather/00.00.03-62/shots/002/shot.mp4`, etc.
PySceneDetect also saves the shots metadata table under `/shots/shots.csv`.

If no parameters (-p) are provided,
the `detect-adaptive` detection method is used.

Applies to all clips in the collections.

## Parameters (-p)

For more information see [PySceneDetect documentation about the various methods](https://www.scenedetect.com/docs/latest/cli.html#detectors`)

* `method`: the scene detection method (`detect-content`, `detect-adaptive` or `detect-threshold`)
* `threshold`: threshold value for `detect-adaptive` or `detect-threshold` methods; pyscene detect default to 12

## Run if

No VIDEO/shots already exists.

## Redo (-r)

Supported.

If first delete the content of the `shots` folder.

## Filtering (-f)

Supported

