# syntax=docker/dockerfile:1.4
FROM python:3.12-slim

WORKDIR /app

# MySQL 8.4 shared client library – required to run worldserver/authserver
# binaries that were compiled against libmysqlclient.so.24.
# The .so file is bundled in libs/ so the image works after any rebuild.
COPY libs/libmysqlclient.so.24.0.8 /usr/lib/x86_64-linux-gnu/libmysqlclient.so.24.0.8

# System deps for aiomysql + psutil + stdbuf (coreutils, for subprocess line-buffering)
# curl is needed for downloading client data files
# Boost libraries are needed for AzerothCore extraction tools (map_extractor, vmap4_*, mmaps_generator)
# Using libboost-all-dev to ensure all required Boost components are available
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    default-mysql-client \
    gcc \
    coreutils \
    curl \
    xz-utils \
    libboost-all-dev \
    && rm -rf /var/lib/apt/lists/*

# Create symlinks AFTER apt so they aren't overwritten by MariaDB's ldconfig hooks.
RUN ln -sf /usr/lib/x86_64-linux-gnu/libmysqlclient.so.24.0.8 \
        /usr/lib/x86_64-linux-gnu/libmysqlclient.so.24 && \
    ln -sf /usr/lib/x86_64-linux-gnu/libmysqlclient.so.24.0.8 \
        /lib/x86_64-linux-gnu/libmysqlclient.so.24 && \
    ldconfig

COPY requirements.txt .

# Use BuildKit cache mount to persist pip cache across builds
# This dramatically speeds up rebuilds as packages are cached
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

