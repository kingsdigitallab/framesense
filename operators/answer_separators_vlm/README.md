# answer_separators_vlm

## Input

* a video file

## Output

* answers in a json file `video_answers.json`: the combined list of the separators between distinct programmes, each with its start and end timecodes (HH:MM:SS, relative to the full video) and a tag describing its nature
* the video chunks in a `chunks/` folder next to the video file, e.g. `chunks/00000000-00000900.mp4`

## Method

The video is split into chunks of `chunk_duration_secs` seconds (15 minutes by default), consecutive chunks overlapping by `chunk_overlap_secs` seconds (2 minutes by default). Chunks are cut with ffmpeg: the seek is fast and the chunk is re-encoded (`libx264`, `veryfast`, crf 28) so that cut points are frame-accurate. Existing chunks are reused across runs.

Each chunk is passed to a VLM behind an openai-compatible API (inherited from [answer_videos_vlm](../answer_videos_vlm/)) with a prompt asking for the list of the separators between distinct programmes: colour bars, test cards, idents, black screens, static, countdown leaders, slates, or any other interstitial, whatever the genre, the source or the decade of the programmes. For each separator the model returns the start and end timecodes relative to the chunk, plus a tag describing its nature.

Timecodes are converted back to the full video and the answers of all the chunks are combined; a separator seen twice (in the overlapping region of two neighbouring chunks) is merged, keeping the longest version.

Applies to all videos in the collections.

## Parameters

Same parameters as [answer_videos_vlm](../answer_videos_vlm/), plus:

* `chunk_duration_secs`: duration of a chunk, in seconds (default: 900)
* `chunk_overlap_secs`: duration of the overlap between two consecutive chunks, in seconds (default: 120)

## Run if

The answer to that same question by the same model over the same video is not found in the output file.

## Redo (-r)

Supported. The chunks are cut again and the questions are asked again.

## Filtering (-f)

Supported
