# transcription_vad_sub

## Input

* clip transcriptions (e.g. `gotdfather/00.00.03-62/transcription.json`,
output of [transcribe_speech_parakeet](../transcribe_speech_parakeet/))
* clip voice segments (e.g. `gotdfather/00.00.03-62/voice_segments.json`,
output of [detect_speech_vad](../detect_speech_vad/))

## Output

* srt subtitle file (e.g. `gotdfather/00.00.03-62/00.00.03-62.srt`)

The transcription segments which do not overlap
any of the voice segments are dropped:
breath, music and other non-speech parts
end up without subtitles.

If a clip has no `voice_segments.json`
(`detect_speech_vad` has not been run on it),
all the transcription segments are kept.

An empty `voice_segments.json` (no voice detected)
results in an empty srt file.

At the end of the run a summary is printed:
how many srt files were created or already existed,
how many clips were skipped,
how many transcriptions were not found,
and how many clips had no voice segments.

## Method

Pure python processing, no model involved:
the srt file is generated from `transcription.json`,
keeping only the segments whose time range
strictly overlaps the time range of a voice segment.

Applies to all clips in the collections.

## Run if

No srt file already exists.

## Redo (-r)

Supported.

## Skip (-k)

Clips whose srt file cannot be created
(e.g. invalid json input file)
are skipped with a warning
and the run continues.

Without -k the operator stops
on the first failing clip.

## Filtering (-f)

Supported

## Resource usage

Negligible: pure python running on the host,
no container, no model.
