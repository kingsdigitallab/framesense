# Use the official Python image with slim version
FROM python:3.12-slim

EXPOSE 5000

# Install dependencies
RUN apt update && \
    apt install -y --no-install-recommends wget vim && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory (will be mounted)
WORKDIR /app
RUN mkdir -p /models
RUN wget -P /models https://github.com/sssabet/Shot_Type_Classification/raw/refs/heads/master/models/Pytorch_Classification_50ep.pt

# Singularity doesn't like /tmp or /app
COPY app/requirements.txt /models/requirements.txt

RUN pip install light-the-torch
RUN ltt install -r /models/requirements.txt

