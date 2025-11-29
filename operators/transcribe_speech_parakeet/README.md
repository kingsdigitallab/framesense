# transcribe_speech_parakeet

## Input

* clips sounds (e.g. `gotdfather/00.00.03-62/00.00.03-62.wav`)

## Output

* text file (e.g. `gotdfather/00.00.03-62/transcription.json`)

## Method

Uses speech-to-text parakeet model

Applies to all clips in the collections.

## Run if

No sound file already exists.

## Redo (-r)

Supported.

## Filtering (-f)

Supported

## Resource usage

The RAM/VRAM usage depends on the size of the model 
and the duration of the input sound file.

If you get an Out of Memory error while using the GPU,
and you have much more RAM than VRAM you may have more luck with
`CUDA_VISIBLE_DEVICES='' python framesense.py extract_sound_ffmpeg`
.
