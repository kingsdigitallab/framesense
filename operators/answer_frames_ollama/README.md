# answer_frames_ollama

## Input

* image of a frame (e.g. `gotdfather/00.00.03-62/shots/001/middle.jpg`)
* a question about the image
* a vision language model

## Output

* answer to the question in `frames.json`

## Method

Uses a vision language model via Ollama inferrence service.

Applies to all frames in the collections.

IMPORTANT: you need to ensure ollama is installed and running.

The required model will be pulled on demand.

## Run if

The answer to that same question by the same model over the same frame is not found in frames.json.

## Redo (-r)

Supported.

## Filtering (-f)

Supported

You can also filter by the name of the frame with the frame_filter param.

## Params

See params.json.

Available vision models on ollama: https://ollama.com/search?c=vision

Example:

* `moondream:1.8b` (3GB of VRAM) is the fatest and runs on low VRAM or CPU
* `gemma3:4b` (5.5GB) and above
* `qwen3-vl:2b` (7.5GB) and above
* `minicpm-v` (7GB VRAM)
