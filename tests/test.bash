#!/bin/bash

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
export FRAMESENSE_DOTENV_PATH='tests/.env'

run_python_script "python framesense.py -h"
run_python_script "python framesense.py collections -v"
run_python_script "python framesense.py annotations"
run_python_script "python framesense.py make_clips_ffmpeg"
run_python_script "python framesense.py extract_sound_ffmpeg"
run_python_script "python framesense.py transcribe_speech_parakeet -r"
run_python_script "python framesense.py make_shots_scenedetect"
run_python_script "python framesense.py make_frames_ffmpeg"
run_python_script "python framesense.py scale_frames_sssabet -r"

echo "-------"
echo "Test suite completed without errors"
