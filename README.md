# FrameSense

FrameSense is command line tool to process your video collections.

## Requirements

* python 3.10+
* Docker or Singularity

## Initial set Up

1. Copy docs/collections.json to the folder containing your video collections and adapt its contents to your needs.
2. Copy docs/.env in this folder and adapt the values to your environment.
3. Create the virtual environment: `python3 -m venv venv`
4. Activate the virtual environment: `source venv/bin/activate`
5. Install the required packages: `pip install -r requirements.txt`

## Expected folder structure of your collections

* COLLECTIONS
    * collections.json
    * COLLECTION1
        * VIDEO1
            * (VIDEO1.mp4)
            * CLIP1
                * CLIP1.mp4
                * shots
                    * SHOT_INDEX # three digits, zero-padded
                        * 01-XXX.jpg # first frame
                        * 02-XXX.jpg # middle frame
                        * 03-XXX.jpg # last frame

## Usage

The tool offers a command-line interface to a series of modular operators acting on your video collections.

To see the list of available operators:

`python framesense.py operators`

For instance, to see the collections and the videos they contain:

`python framesense.py collections -v`

## Principles

* modular: each operation has its own module and dependencies; easy to extend or swap operations;
* incremental: an operation builds on top of outputs from other operations, enabling caching, reuse of intermediate results and custom pipelines;
* hpc-friendly: non-interactive command line tool which is easy to install and run on SLURM;
* portable: should be easy to run on different machines, including lower-end personal computers

## TODO

* make_clips_ffmpeg: test with Singularity
* make_clips_ffmpeg: docker -rm to delete container on exit
* make_frames: new operator
* make_clips_ffmpeg: remove clip folders which are no longer annotated


