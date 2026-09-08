FROM linuxserver/ffmpeg

# libass needs actual fonts to burn the subtitles onto the clips
RUN apt-get update && \
    apt-get install -y --no-install-recommends fontconfig fonts-dejavu-core && \
    rm -rf /var/lib/apt/lists/*

ENTRYPOINT []
