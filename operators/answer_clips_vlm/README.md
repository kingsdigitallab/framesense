# answer_clips_vlm

## Input

* a clip file
* a set of questions

## Output

* answers in a json file `clip_answers.json` placed alongside each clip

## Method

Uses video language model behind an openai-compatible inferrence engine.

Applies to all clips in the collections.

## Run if

The answer to that same question by the same model over the same clip is not found in the output file.

## Redo (-r)

Supported.

## Filtering (-f)

Supported
