FROM linuxserver/ffmpeg

# tesseract and its English language data detect the burned-in subtitles in the clip samples
RUN apt-get update && \
    apt-get install -y --no-install-recommends tesseract-ocr && \
    rm -rf /var/lib/apt/lists/*

ENTRYPOINT []
