# Use the official Python image with slim version
FROM python:3.12-slim

EXPOSE 5000

# Install dependencies
RUN apt update && \
    apt install -y --no-install-recommends wget vim build-essential && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory (will be mounted)
WORKDIR /app
RUN mkdir -p /models

# Singularity doesn't like /tmp or /app
COPY app/requirements.txt /models/requirements.txt

RUN pip install -U pip setuptools wheel
RUN pip install -r /models/requirements.txt

ENV HF_HOME=/hf_cache
