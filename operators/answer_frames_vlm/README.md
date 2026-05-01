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

Examples for 6 frames on a laptop w/ i7-1260P Intel (16 Cores), 32GB RAM, 4GB VRAM:

| Model | VRAM (GB) | GPU processing (s.) | CPU only
|----------|----------|----------|----------|
| `moondream:1.8b` | 1.1 | 34 | 116 |
| `gemma3:4b` | 4.3 | 80 | 516 |
| `gemma4:e2b` | 7.6 | 95 | 224 |
| `ministral-3:3b` | 4.3 | 97 | 649
| `qwen3-vl:2b` | 3.0 | 106 | 486 |
| `qwen3.5:0.8b` | 2.3 | 130 | 347 |
| `qwen3.5:2b` | 4.5 | 283 | 656 | 
