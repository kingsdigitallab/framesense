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

Supported models:
* [jinaai/jina-clips-v2 (2024)](https://huggingface.co/jinaai/jina-clip-v2)
* [jinaai/jina-embeddings-v4 (2025)](https://huggingface.co/jinaai/jina-embeddings-v4)

|           | jina-clips-v2  | jina-embeddings-v4 |
| --------- | -------------- | ------------------ |
| params    | 0.9B           | 3.8B               |
| release   | Dec 2024       | June 2025          |
| vec size  | 1024           | 2048               |
| img size  | 512x512 pixels | 20 mega pixels     |
| sec/img   | ~3s on CPU     | ~120s on CPU       |

Set environment variable `CUDA_VISIBLE_DEVICES=''` 
to force the use of a CPU in case your GPU doesn't have enough VRAM.

