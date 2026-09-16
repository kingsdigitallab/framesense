# separate_clips_ffmpeg

## Input
* clips (C/C.mp4) in the video folders of a collection
* video_answers.json with a sep1 answer listing the programme separators of each video

## Output
* -prog clips (P/P.mp4) placed in sibling folders of the original clip

## Method
Use ffmpeg to split each clip into new clips around the programme separators
listed in the sep1 answer of the video_answers.json of the video it belongs to.

Separator timecodes are assumed to be relative to the beginning of each clip
(no offset, the start or duration of the clip is not used to place them).

Each new clip is split into:
* a head segment before the first separator (if any)
* one segment between each pair of consecutive separators
* a tail segment after the last separator (if any)

Segments shorter than the `min_segment_seconds` parameter (default 1 second)
are discarded.

New clips keep the suffix of the original clip and add the `-prog` suffix:
* `00.00.00-3717-full` split into `00.00.19-1267-full-prog`, `00.21.28-2022-full-prog`, ...
* `00.21.26-2` without separator kept as is: `00.21.26-2-prog`

A clip without any separator in it is symlinked as a single `-prog` clip.

The `cut_mode` parameter selects how each -prog clip is cut:
* `smart` (default): second-accurate with a non-lossy image quality. The whole
  segment is re-encoded in a single ffmpeg command with a non-lossy `crf`
  (default 0) and `-preset ultrafast`, while its audio stream is copied. A
  single stream is produced, so the -prog clip is always playable.
  Falls back to `reencode` when ffmpeg fails.
* `reencode`: the whole segment is re-encoded by ffmpeg, second-accurate but
  lossy.

## Parameters (-p)
* `min_segment_seconds` (int, default 1): minimum length in seconds of a new -prog clip
* `cut_mode` (str, default smart): `smart` for a second-accurate non-lossy cut, `reencode` to re-encode the whole segment
* `smart_crf` (int, default 0): `crf` of the video re-encoding of the `smart` cut, 0 being visually lossless; higher values trade image quality for speed and file size

## Run if
A -prog clip does not already exist for a segment.

## Redo (-r)
Will recreate the -prog clips, removing existing -prog clip files first.