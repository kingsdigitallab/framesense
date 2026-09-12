# detect_speech_vad

## Input

* clips sounds (e.g. `gotdfather/00.00.03-62/00.00.03-62.wav`)

## Output

* text file (e.g. `gotdfather/00.00.03-62/voice_segments.json`)

An array of the segments (in seconds) of the clip where a voice is detected:

```json
[
    {
        "start": 4.96,
        "end": 9.28
    },
    {
        "start": 10.4,
        "end": 15.12
    }
]
```

An empty array means no voice was detected in the clip.

At the end of the run a summary is printed:
how many voice segment files were created or already existed,
how many clips were skipped,
and how many sound files were not found.

## Method

Uses the silero-vad voice activity detection model
bundled in the `silero-vad` python package
(installed in the operator's container image,
along with FFmpeg to decode the sound files).

Applies to all clips in the collections.

Runs on CPU only: the model is tiny (~2 MB)
and detection takes ~1 ms per 30 ms of sound on a single CPU thread.

## Parameters

* `threshold`: speech probability threshold above which a frame is
considered speech (default `0.65`).
* `min_silence_duration_ms`: silence shorter than this duration does not
split two consecutive voice segments (default `500`).

They can be overridden in the `params` of the collections file,
in the `params` of a pipeline operation,
or with the environment variables `DETECT_SPEECH_VAD_THRESHOLD`
and `DETECT_SPEECH_VAD_MIN_SILENCE_DURATION_MS`.

## Run if

No voice segment file already exists.

## Redo (-r)

Supported.

## Skip (-k)

Clips whose voice segments cannot be detected
are skipped with a warning
and the run continues.
No voice segment file is written for them,
so they are processed again on the next run.

Without -k the operator stops
on the first failing clip.

## Filtering (-f)

Supported

## Resource usage

The model is small and runs on CPU,
so the RAM usage stays low (well under 1 GB).

The container image is ~1.5 GB
(CPU-only torch wheels).
