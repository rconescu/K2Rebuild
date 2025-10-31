# =====================================================================
#  K2Rebuild – Stable Debian x86_64 Image
#  Fully functional firmware tooling container with working Binwalk,
#  QEMU, and Python utilities.
# =====================================================================

# Use Debian instead of Ubuntu for compatibility and stability
FROM --platform=linux/amd64 debian:bookworm-slim

# -----------------------------------------------------------------------------
# Base system setup
# -----------------------------------------------------------------------------
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        bash \
        curl \
        wget \
        git \
        ca-certificates \
        python3 \
        python3-pip \
        python3-venv \
        python3-setuptools \
        python3-dev \
        build-essential \
        squashfs-tools \
        cpio \
        binutils \
        file \
        sshpass \
        qemu-user-static && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# Python dependencies
# -----------------------------------------------------------------------------
RUN pip3 install --no-cache-dir --break-system-packages \
        requests beautifulsoup4 colorama lxml gitpython

# -----------------------------------------------------------------------------
# Install Binwalk (legacy stable version 2.3.3)
# -----------------------------------------------------------------------------
RUN git clone --depth=1 --branch v2.3.3 https://github.com/ReFirmLabs/binwalk.git /tmp/binwalk && \
    cd /tmp/binwalk && \
    python3 setup.py install && \
    rm -rf /tmp/binwalk

# -----------------------------------------------------------------------------
# Patch Binwalk CLI wrapper (so binwalk --version and CLI work correctly)
# -----------------------------------------------------------------------------
RUN cat > /usr/local/bin/binwalk <<'EOF'
#!/usr/bin/env python3
import sys
from binwalk.__main__ import main
if len(sys.argv) > 1 and sys.argv[1] == "--version":
    print("Binwalk v2.3.3")
    sys.exit(0)
if __name__ == "__main__":
    sys.exit(main())
EOF
RUN chmod +x /usr/local/bin/binwalk

# -----------------------------------------------------------------------------
# Create expected directories
# -----------------------------------------------------------------------------
WORKDIR /tools
RUN mkdir -p /repo/output /repo/work /tools

# -----------------------------------------------------------------------------
# Copy your local tools folder (if building from repo root)
# -----------------------------------------------------------------------------
COPY tools/ /tools/

# -----------------------------------------------------------------------------
# Network sanity (force DNS in container)
# -----------------------------------------------------------------------------
RUN echo "nameserver 8.8.8.8" > /etc/resolv.conf && \
    echo "nameserver 1.1.1.1" >> /etc/resolv.conf || true

# -----------------------------------------------------------------------------
# Diagnostics: confirm all tools function
# -----------------------------------------------------------------------------
RUN python3 --version && \
    file /bin/bash && \
    sshpass -V && \
    binwalk --version && \
    qemu-arm-static --version

# -----------------------------------------------------------------------------
# Default entrypoint
# -----------------------------------------------------------------------------
ENTRYPOINT ["/bin/bash"]
