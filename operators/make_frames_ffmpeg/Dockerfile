# Use the official Python image with slim version
FROM python:3.12-slim

# Install FFmpeg and other necessary dependencies
# apt-get install -y --no-install-recommends ffmpeg git libmagic-dev && \
RUN apt update && \
    apt install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
# WORKDIR /app

# Copy the requirements file and install Python dependencies
## COPY requirements.txt /tmp/.
## RUN pip install --no-cache-dir -r requirements.txt

RUN pip install scenedetect[opencv]==0.6.6

# Copy the rest of the application code
# COPY . .

# Command to run PySceneDetect
CMD ["scenedetect", "--help"]
