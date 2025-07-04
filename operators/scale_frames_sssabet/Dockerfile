# Use the official Python image with slim version
FROM python:3.12-slim

# Install dependencies
RUN apt update && \
    apt install -y --no-install-recommends wget vim && \
    echo "REMOVE THIS"
    ## rm -rf /var/lib/apt/lists/*

# Set the working directory
COPY ./app /app
WORKDIR /app

RUN pip install light-the-torch
RUN ltt install -r requirements.txt

RUN mkdir /models
RUN wget -P /models https://github.com/sssabet/Shot_Type_Classification/raw/refs/heads/master/models/Pytorch_Classification_50ep.pt

# Copy the rest of the application code
# COPY . .

# Command to run PySceneDetect
# CMD ["scenedetect", "--help"]
