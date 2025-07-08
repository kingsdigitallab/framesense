# scale_frames_sssabet

## Input

* frames (C/C/*.jpg)
* collections (collections.json)

Please make sure the frames are organized under shot folders within each collection.

## Output

* frames with scale classification metadata (C/C/frames.json)

## Method

Use a frame scale classifier based on //github.com/sssabet/Shot_Type_Classification
to determine the scale of each frame and update the frames' metadata files accordingly.

Applies to all frames in the collections.

## Parameters (-p)

Not supported

## Run if

The frame scale classification is not already present in the metadata file (frames.json).

Note that if you add new frames or change the classifier, only those frames will be classified.

## Residue

Frames which are no longer included in the collections will remain on disk with their existing metadata.

## Redo (-r)

Will recreate the frame scale classification for all frames,
but won't remove existing data under the frames folders.
