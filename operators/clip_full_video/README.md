# clip_full_video

## Input

* videos (V/V.mp4)

## Output

* clips (C/C.mp4)

At the end of the run a summary is printed:
how many clips were created or already existed,
and how many videos were skipped.

## Method

For each video V/V.mp4,
create a clip C covering the whole video
by symlinking the video file:

V/00.00.00-D-full/00.00.00-D-full.mp4 -> ../V.mp4

where D is the duration of the video in seconds.

The clip and its folder are named after
the clip's start time code (00.00.00)
and the video duration in seconds,
following the same naming convention
as the clips made by make_clips_ffmpeg,
with the -full tag appended to mark the clip
as covering the whole video.

The symlink is relative,
so the collection can be moved or copied
without breaking the link.

The container is only used for ffprobe,
which reads the video duration.

## Parameters

Not supported

## Run if

The clip (C/C.mp4) does not already exist.

To save time the video duration is not read
when the video folder already contains
a full clip folder (00.00.00-*-full) with its clip file in it.
Use -r to process the video anyway,
for instance if the video file has changed since.

## Residue

Full clips created by a previous version
(without the -full tag in their name)
remain on disk after a new run.
They can be removed manually.

## Redo (-r)

Will remove and recreate the symlink,
leaving any other file in the clip folder untouched.

## Skip (-k)

Videos whose duration cannot be read
(e.g. corrupted or truncated files)
are skipped with a warning
and the run continues.

Without -k the operator stops
on the first unreadable video.
