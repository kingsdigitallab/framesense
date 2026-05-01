#!/bin/bash

SCENARIO="$1"
VIDEO_FILTER="1"
VIDEO_FILTER="Park"
#VIDEO_FILTER="Trees"

run_python_script() {
    local python_command="$1"
    echo "=========================================="
    echo $python_command
    eval "$python_command"
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo "Error: The Python script failed with exit code $exit_code."
        exit 1
    fi
}

if [ ! -d "collections" ]; then
    cp -r original_collections collections
fi

cd ..
export FRAMESENSE_DOTENV_PATH='workshop/.env'

run_python_script "python framesense.py make_clips_ffmpeg -f $VIDEO_FILTER"
# run_python_script "python framesense.py make_shots_scenedetect -f $VIDEO_FILTER"
# run_python_script "python framesense.py make_frames_ffmpeg -f $VIDEO_FILTER"
# run_python_script "python framesense.py scale_frames_sssabet -f $VIDEO_FILTER"
# run_python_script "python framesense.py answer_frames_vlm -f $VIDEO_FILTER"

echo "-------"
echo "Test suite completed without errors"
