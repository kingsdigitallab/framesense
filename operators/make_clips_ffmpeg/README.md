# make_clips_ffmpeg

## Input

* annotation files (V.json)
* videos (V/X.mp4)

Please make sure the name of the annotation file matches the name of the video folder it relates to.

You can use the `annotations -v` operator to find out mismatches.

## Output

* clips (C/C.mp4)

## Method

Use ffmpeg to extract a clip 
from a video V/X.mp4
using the start and end timecodes 
specified in the annotation file 
which name matches the video (V.json)

Applies to annotations 
in all annotation files.

## Parameters (-p)

Not supported

## Run if

The clip (C/C.mp4) does not already exist.

Note that if you change the time codes in the annotation files or add new annotations, only those clips will be extracted.

## Residue

Extracted clips which are no longer included (with same time codes) in the annotation files will remain on disk.

## Redo (-r)

Will recreate the .mp4 clips, 
but won't remove existing data under the clip folders.


