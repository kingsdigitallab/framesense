# Use the official Python image with slim version
FROM python:3.12-slim

# EXPOSE 5000

# Install dependencies
RUN apt update && \
    apt install -y --no-install-recommends wget vim build-essential && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory (will be mounted)
WORKDIR /app

# Singularity doesn't like /tmp or /app
COPY app/requirements.txt /requirements.txt

RUN pip install -U pip setuptools wheel
RUN pip install -r /requirements.txt

# ARG USER_ID
# ARG GROUP_ID
# RUN groupadd -g $GROUP_ID user && \
#     useradd -u $USER_ID -g user -m user
# USER user
