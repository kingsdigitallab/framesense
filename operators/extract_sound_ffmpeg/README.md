# extract_sound_ffmpeg

## Input

* clips (e.g. `gotdfather/00.00.03-62/00.00.03-62.mp4`)

## Output

* sound file (e.g. `gotdfather/00.00.03-62/00.00.03-62.wav`)

At the end of the run a summary is printed:
how many sound files were created or already existed,
and how many clips were skipped.

## Method

Uses ffmpeg.

Applies to all clips in the collections.

## Run if

No sound file already exists.

## Redo (-r)

Supported.

## Skip (-k)

Clips which sound cannot be extracted from
(e.g. corrupted or truncated files)
are skipped with a warning
and the run continues.
The partial sound file of a failed clip is removed,
so it is extracted again on the next run.

Without -k the operator stops
on the first failing clip.

## Filtering (-f)

Supported

