# syntax=docker/dockerfile:1
FROM debian:bookworm

LABEL org.opencontainers.image.title="K2Rebuild" \
      org.opencontainers.image.description="Creality K2 Plus firmware analysis and rebuild toolkit" \
      org.opencontainers.image.authors="Your Name <you@example.com>" \
      org.opencontainers.image.source="https://github.com/<yourusername>/K2Rebuild"

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# -----------------------------------------------------------------------------
# Install system dependencies for firmware analysis and Python tooling
# -----------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    binwalk \
    squashfs-tools \
    kpartx \
    partx \
    dosfstools \
    mtools \
    qemu-user-static \
    debootstrap \
    binfmt-support \
    u-boot-tools \
    xz-utils \
    tar \
    rsync \
    wget \
    curl \
    unzip \
    python3 \
    python3-pip \
    git \
    build-essential \
    parted \
    fdisk \
    util-linux \
    e2fsprogs \
    iputils-ping \
    netbase \
    gzip \
    bzip2 \
    cpio \
    bc \
    file \
    gettext \
    sfdisk \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# Install Python dependencies
# -----------------------------------------------------------------------------
RUN python3 -m pip install --no-cache-dir --upgrade pip requests beautifulsoup4 pyyaml

# -----------------------------------------------------------------------------
# Copy core tools into container
# -----------------------------------------------------------------------------
COPY fwtool.sh /usr/local/bin/k2rebuild-fwtool
COPY tools/download_latest_k2plus_fw.py /usr/local/bin/download_latest_k2plus_fw
COPY tools/firmware_validator.py /usr/local/bin/firmware_validator
RUN chmod +x /usr/local/bin/k2rebuild-fwtool /usr/local/bin/download_latest_k2plus_fw /usr/local/bin/firmware_validator

# -----------------------------------------------------------------------------
# Define the working directories
# -----------------------------------------------------------------------------
# /repo is the mounted host repository
# /repo/output is where all logs, downloads, and build artifacts will live
WORKDIR /repo
ENV K2_OUTPUT_DIR=/repo/output

# -----------------------------------------------------------------------------
# Ensure all tooling writes logs and downloads to host-mapped output directory
# -----------------------------------------------------------------------------
RUN mkdir -p $K2_OUTPUT_DIR && \
    ln -sfn $K2_OUTPUT_DIR /work && \
    ln -sfn $K2_OUTPUT_DIR /usr/data && \
    ln -sfn $K2_OUTPUT_DIR /usr/data/logs

VOLUME ["/repo"]

ENTRYPOINT ["/usr/local/bin/k2rebuild-fwtool"]
CMD ["help"]
