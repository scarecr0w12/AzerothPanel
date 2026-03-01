# syntax=docker/dockerfile:1.4
FROM python:3.12-slim

WORKDIR /app

# MySQL 8.4 shared client library – required to run worldserver/authserver
# binaries that were compiled against libmysqlclient.so.24.
# The .so file is bundled in libs/ so the image works after any rebuild.
COPY libs/libmysqlclient.so.24.0.8 /usr/lib/x86_64-linux-gnu/libmysqlclient.so.24.0.8

# Step 1: minimal tools needed to add the Oracle MySQL APT repo.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gnupg \
    ca-certificates \
    lsb-release \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Step 2: add Oracle MySQL 8.0 APT repo.
# AzerothCore's MySQLConnection.cpp uses `mysql_ssl_mode` (SSL_MODE_DISABLED),
# which is an Oracle-only enum — it does NOT exist in MariaDB's headers.
# Using default-libmysqlclient-dev (MariaDB) therefore causes a fatal build error.
# mysql-apt-config with DEBIAN_FRONTEND=noninteractive selects MySQL 8.0 by default.
# NOTE: Oracle's MySQL APT signing key expired 2025-10-22. We patch the generated
# apt sources entry to [trusted=yes] so apt-get update works in this controlled
# build environment without needing a refreshed key.
RUN wget -q https://dev.mysql.com/get/mysql-apt-config_0.8.33-1_all.deb \
         -O /tmp/mysql-apt-config.deb \
    && DEBIAN_FRONTEND=noninteractive dpkg -i /tmp/mysql-apt-config.deb \
    && rm /tmp/mysql-apt-config.deb \
    && sed -i 's|\[signed-by=[^]]*\]|[trusted=yes]|g' \
            /etc/apt/sources.list.d/mysql.list

# Step 3: install all remaining deps — Oracle MySQL dev headers replace MariaDB's.
# curl/wget are needed for downloading client data files and MySQL APT config.
# git is required for cloning AzerothCore and installing modules at any time.
# Build tools (cmake, make, gcc, g++, clang) and dev libs are pre-installed so
# that module installation, compilation, and the installer's apt steps all work
# without needing a separate apt-get install at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Oracle MySQL 8.x client + dev headers (defines mysql_ssl_mode / SSL_MODE_DISABLED)
    libmysqlclient-dev \
    mysql-client \
    # Core utilities
    coreutils \
    curl \
    xz-utils \
    # Version control
    git \
    # C/C++ build toolchain
    gcc \
    g++ \
    clang \
    cmake \
    make \
    # AzerothCore build dependencies
    libssl-dev \
    libbz2-dev \
    libreadline-dev \
    libncurses-dev \
    libboost-all-dev \
    && rm -rf /var/lib/apt/lists/*

# Create symlinks AFTER apt so they aren't overwritten by ldconfig hooks.
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

