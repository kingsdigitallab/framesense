# transcribe_speech_parakeet

## Input

* clips sounds (e.g. `gotdfather/00.00.03-62/00.00.03-62.wav`)

## Output

* text file (e.g. `gotdfather/00.00.03-62/transcription.json`)

At the end of the run a summary is printed:
how many transcriptions were created or already existed,
how many clips were skipped,
and how many sound files were not found.

## Method

Uses speech-to-text parakeet model

Applies to all clips in the collections.

## Run if

No transcription file already exists.

## Redo (-r)

Supported.

## Skip (-k)

Clips which sound cannot be transcribed
are skipped with a warning
and the run continues.
No transcription file is written for them,
so they are transcribed again on the next run.

Without -k the operator stops
on the first failing clip.

## Filtering (-f)

Supported

## Resource usage

The RAM/VRAM usage depends on the size of the model 
and the duration of the input sound file.

If you get an Out of Memory error while using the GPU,
and you have much more RAM than VRAM you may have more luck with
`TRANSCRIBE_SPEECH_PARAKEET_CPU_ONLY=1 python framesense.py transcribe_speech_parakeet`
.
