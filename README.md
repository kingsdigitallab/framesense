# FrameSense

FrameSense is command line tool to process your video collections.

## Requirements

* python 3.10+
* Docker or Singularity

## Initial set Up

1. Clone this repository anywhere on your system;
2. Copy [`docs/collections.json`](docs/collections.json) to the folder containing your video collections and adapt its contents to your needs. All paths `collections.json` are relative to that file.
3. Copy [`docs/.env`](docs/.env) in the folder that contains `framesense.py` and adapt the values to your environment. `FRAMESENSE_COLLECTIONS` should be the absolute path to your copy of `collections.json`.
4. Create the python virtual environment: `python3 -m venv venv`
5. Activate the virtual environment: `source venv/bin/activate`
6. Install the required packages: `pip install -r requirements.txt`

## Concepts

In FrameSense your collection is broken down into a hierachy of smaller units. A `Collection` contains `videos`, which are made of `Clips`. Each Clip is a string of `Shots`. And each Shot is composed of a series of `Frames`.

Each operation provided by FrameSense works at on a particular unit in that hierarchy.

A video can be manually annotated in an `annotation file` that contains a list of annotations. An `annotation` describes and locates a clip within the video.

## Expected folder structure of your collections

* COLLECTIONS
    * collections.json*
    * COLLECTION1*
        * VIDEO1*
            * VIDEO1.mp4
            * CLIP1
                * CLIP1.mp4
                * shots
                    * SHOT_INDEX # three digits, zero-padded
                        * 01-XXX.jpg # first frame
                        * 02-XXX.jpg # middle frame
                        * 03-XXX.jpg # last frame

In the above tree, a file or folder name in capital can be name whichever way you like. 
File or folder with an asterisk are mandatory. Names in lowercase are predefined, you can't change them.
Initially each video folder must have either a video file (e.g. godfather/godfather.mp4) or one (or more) clips (e.g. godfather/godfather/baptism/baptism.mp4).

## Usage

The tool offers a command-line interface to a series of modular operators acting on your video collections.

To see the list of available operators:

`python framesense.py operators`

For instance, to see the collections and the videos they contain:

`python framesense.py collections -v`

## Principles

* **Modular**: each operation has its own module and dependencies; easy to extend or swap operations;
* **Incremental**: an operation builds on top of outputs from other operations, enabling caching, reuse of intermediate results and custom pipelines;
* *HPC-friendly**: non-interactive command line tool which is easy to install and run on SLURM;
* **Portable**: should be easy to run on different machines, including lower-end personal computers

## Operators

FrameSense comes with a battery of built-in operators. 

It is expected that each operator:
* is atomic or minimal ("does one thing and does it well");
* implements one method or strategy;
* should only process the input of its output doesn't already exist;
* uses containers isolate its software dependencies;
* works on all files at one specific level in the hierarchy (e.g. make_shots splits all your clips into shots);
* has a name which reflects what it does, on what unit, with which method (e.g. make_clips_ffmpeg);
* is written as Python class wihin a module `operator.py` under a package which name matches the name of the operator (e.g. `operators/make_clips_ffmpeg/operator.py`);
* inherits from the [base operator](operators/base/operator.py);


## TODO

* make_clips_ffmpeg: test with Singularity
* make_clips_ffmpeg: docker -rm to delete container on exit
* make_frames: new operator
* make_clips_ffmpeg: remove clip folders which are no longer annotated
* add filter options

