# embed_frames-transformers

## Input

* image of a frame (e.g. `gotdfather/00.00.03-62/shots/001/middle.jpg`)
* a vision language model

## Output

Vector representing the frame added to frames.json under key 'embedding'.

Vector size will depend on the model. jina models returns truncable vectors.
Matryoshka dimensions: 128, 256, 512, 1024, 2048

## Method

Uses an embedding model via Transfomers framework.

Applies to all frames in the collections.

The required model will be pulled on demand.

## Run if

The embedding of the same frame by the same model is not found in frames.json.

## Redo (-r)

Supported.

## Filtering (-f)

Supported

You can also filter by the name of the frame with the frame_filter param.

## Params

See params.json.

Available models:
* [jinaai/jina-clips-v2 (2024)](https://huggingface.co/jinaai/jina-clip-v2): requires ? of VRAM or ~5GB of RAM (without GPU). Returned vector has 1024 dimensions.
* [jinaai/jina-embeddings-v4 (2025)](https://huggingface.co/jinaai/jina-embeddings-v4): requires ~18GB of VRAM or 8GB of RAM (without GPU). Returned vector has 2048 dimensions.

Set environment variable `CUDA_VISIBLE_DEVICES=''` 
to force the use of a CPU in case your GPU doesn't have enough VRAM.
