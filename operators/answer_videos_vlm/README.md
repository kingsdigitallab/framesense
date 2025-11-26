# answer_videos_vlm

## Input

* a video file
* a set of questions

## Output

* answers in a json file `video_answers.json`

## Method

Uses Qwen video language model run with Hugging face transformers API.

Applies to all videos in the collections.

Note that qwen models require a GPU with a lot of VRAM (60-85 GB).
We recommend qwen3-vl-32b-instruct for best results.

## Run if

The answer to that same question by the same model over the same video is not found in the output file.

## Redo (-r)

Supported.

## Filtering (-f)

Supported

