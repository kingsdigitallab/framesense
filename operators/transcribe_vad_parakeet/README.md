# transcribe_vad_parakeet

## Input

* clips sounds (e.g. `gotdfather/00.00.03-62/00.00.03-62.wav`)
* voice segments (e.g. `gotdfather/00.00.03-62/voice_segments.json`, produced by [detect_speech_vad](../detect_speech_vad))

A variant of [transcribe_speech_parakeet](../transcribe_speech_parakeet)
which requires detect_speech_vad to have run first:
clips without a voice_segments.json are reported as missing.

## Output

* text file (e.g. `gotdfather/00.00.03-62/transcription.json`),
in the same format as the one of transcribe_speech_parakeet.

At the end of the run a summary is printed:
how many transcriptions were created or already existed,
how many clips were skipped,
and how many sound or voice segments files were not found.

## Method

Uses the same speech-to-text parakeet model
as [transcribe_speech_parakeet](../transcribe_speech_parakeet),
but transcribes only the voice segments listed in voice_segments.json,
which saves the time spent transcribing its non-speech parts.

For each clip the processor compacts the voice segments into a single
temporary wav (separated by a short silence), which is transcribed in a
single model call; the timecodes of the returned segments are mapped back
into the timecodes of the clip sound, and any segment landing into the
inserted silences, i.e. hallucinated text, is dropped.

Clips whose voice_segments.json is empty result in an empty
transcription.json, without the transcription service being called at all.

Unlike transcribe_speech_parakeet, which passes through the character
offsets of the model, start_offset and end_offset are recomputed to index
the transcript made of the returned segments joined by a single space.

Applies to all clips in the collections.

## Parameters

* `segments_gap_seconds` (default 0.25):
duration of the silences inserted between the voice segments
of the temporary wav.

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
and on the total duration of the voice segments of the input sound.

If you get an Out of Memory error while using the GPU,
and you have much more RAM than VRAM you may have more luck with
`TRANSCRIBE_VAD_PARAKEET_CPU_ONLY=1 python framesense.py transcribe_vad_parakeet`
.
