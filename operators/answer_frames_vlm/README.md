# answer_frames_vlm

## Input

* image of a frame (e.g. `gotdfather/00.00.03-62/shots/001/middle.jpg`)
* a question about the image
* a vision language model

## Output

* answers to the questions in `frames.json`

## Method

Uses a vision language model via an OpenAI-compatible inferrence service.

Applies to all frames in the collections.

IMPORTANT: you need to ensure the service is running at the provided address
(`api_base`).
And the model is available through that service. You may use a cloud service 
or a local inference engine like Ollama.

## Run if

The answer to that same question by the same model over the same frame is not found in frames.json.

## Redo (-r)

Supported.

## Filtering (-f)

Supported

You can also filter by the name of the frame with the frame_filter param.

## Params

See [params.json](params.json).

Examples of vision models on ollama: https://ollama.com/search?c=vision

Example:

* `moondream:1.8b` (1.1GB of VRAM) is the fatest
* `qwen3.5:0.8b` (2.3GB VRAM) and above
* `qwen3-vl:2b` (3GB) and above
* `gemma3:4b` (4.2GB) and above
