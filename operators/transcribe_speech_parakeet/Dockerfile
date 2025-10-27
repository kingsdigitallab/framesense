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

COPY app/processor.py /models/processor.py
RUN python /models/processor.py load_model
RUN rm /models/processor.py

RUN groupadd --gid 1000 u1000 && useradd --uid 1000 --gid 1000 -m u1000
