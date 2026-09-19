# answer_clips_qwen3vl

## Input

* a clip file
* a set of questions

## Output

* answers in a json file `clip_answers.json` placed alongside each clip

## Method

Uses Qwen video language model run with Hugging face transformers API.

Applies to all clips in the collections.

Note that qwen models require a GPU with a lot of VRAM (60-85 GB).
We recommend qwen3-vl-32b-instruct for best results.

## Run if

The answer to that same question by the same model over the same clip is not found in the output file.

## Redo (-r)

Supported.

## Filtering (-f)

Supported
