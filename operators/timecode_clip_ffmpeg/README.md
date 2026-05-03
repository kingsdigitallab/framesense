# timecode_clip_ffmpeg

## Input

* clips (C/C.mp4)

## Output

* timecoded clips (C/C_timecoded.mp4)

## Method

Uses ffmpeg's drawtext filter to overlay a running SMPTE timecode (HH:MM:SS:FF) to the top left corner of every frame of a clip. The frame rate of the output video matches the source video.

## Parameters (-p)

* `fontsize`: font size of the timecode text (default: 24)

## Run if

The timecoded clip (C/C_timecoded.mp4) does not already exist.

## Redo (-r)

Will recreate the timecoded clip with a fresh ffmpeg pass.
