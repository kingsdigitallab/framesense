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
how many were recreated because they were stale,
how many clips were skipped,
how many transcriptions were not found,
how many clips had no voice segments,
and how many cues were dropped by the
hallucination filters (short-overlap and repeated).

## Method

Pure python processing, no model involved:
the srt file is generated from `transcription.json`,
keeping only the segments which overlap the time range
of a voice segment by at least `min_overlap_seconds`.

To remove the hallucinations of the transcription model
which survive the voice filtering, two additional filters
are applied:

* short-overlap: a segment overlapping a voice segment
  by less than `min_overlap_seconds` is dropped
  (these are usually single-word blips);
* repeated: runs of at least `max_repeat_run`
  consecutive identical segments (after normalizing
  text case and punctuation) are collapsed into a
  single segment, which removes the looping
  hallucinations of the transcription model
  (e.g. "I don't know." repeated dozens of times).
  Scattered repeats are kept, as they are more
  likely genuine repetitions.

An existing srt file is recreated when it is stale,
i.e. older than its `transcription.json`
(or `voice_segments.json`, when present):
this makes previously unfiltered srt files
voice-filtered once their inputs are updated.

Applies to all clips in the collections.

## Parameters

* `min_overlap_seconds`: minimum overlap (in seconds)
  between a transcription segment and a voice segment
  for the segment to be kept, to discard single-word
  hallucinations on short voice detections (default `0.25`).
* `max_repeat_run`: runs of at least this many
  consecutive identical segments are collapsed to a
  single segment (default `3`).

They can be overridden in the `params` of the collections file,
in the `params` of a pipeline operation,
or with the environment variables
`TRANSCRIPTION_VAD_SUB_MIN_OVERLAP_SECONDS`
and `TRANSCRIPTION_VAD_SUB_MAX_REPEAT_RUN`.

## Run if

No srt file already exists, or the existing one is stale.

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
