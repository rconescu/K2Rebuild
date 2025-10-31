#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_device_state.py — safely gather runtime metadata from a Creality printer
without downloading binaries or modifying the device.

Purpose:
  • Verify SSH access
  • Collect diagnostic metadata (OS, kernel, partitions, mounts, hardware info)
  • Save results under /repo/output/device_state
  • Update checkpoint.json for orchestration
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from colorama import Fore, Style

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------
OUT_DIR = Path("/repo/output")
STATE_DIR = OUT_DIR / "device_state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_FILE = OUT_DIR / "checkpoint.json"

# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------
def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def info(msg):
    print(f"{Fore.CYAN}[fetch]{Style.RESET_ALL} {msg}")

def warn(msg):
    print(f"{Fore.YELLOW}[fetch]{Style.RESET_ALL} ⚠️ {msg}")

def err(msg):
    print(f"{Fore.RED}[fetch]{Style.RESET_ALL} ❌ {msg}", file=sys.stderr)

def run(cmd, **kw):
    """Run a subprocess safely (binary-safe)."""
    kw.setdefault("stdout", subprocess.PIPE)
    kw.setdefault("stderr", subprocess.STDOUT)
    result = subprocess.run(cmd, **kw)
    return result

def safe_decode(b: bytes) -> str:
    """Decode bytes to UTF-8 safely, ignoring binary garbage."""
    try:
        return b.decode("utf-8", errors="ignore")
    except Exception:
        return ""

def ssh_cmd(host, user, port, password, remote_cmd):
    """Build an ssh command using sshpass for password auth."""
    return [
        "sshpass", "-p", password,
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "PreferredAuthentications=password",
        "-p", str(port),
        f"{user}@{host}",
        remote_cmd,
    ]

def save_checkpoint(stage="fetch_metadata_complete", meta=None):
    """Write progress checkpoint for orchestrator."""
    data = {
        "stage": stage,
        "ts": now(),
        "meta": meta or {},
    }
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ---------------------------------------------------------------------
# Metadata collection
# ---------------------------------------------------------------------
def collect_metadata(args):
    """Collect OS, kernel, and hardware metadata from printer."""
    info("🧠 Collecting metadata from printer...")

    commands = {
        "os_release": "cat /etc/os-release 2>/dev/null || true",
        "kernel": "uname -a",
        "device_model": "cat /proc/device-tree/model 2>/dev/null || true",
        "compatible": "cat /proc/device-tree/compatible 2>/dev/null || true",
        "partitions": "cat /proc/partitions 2>/dev/null || true",
        "mounts": "mount",
        "modules": "lsmod 2>/dev/null || true",
        "inputs": "ls /dev/fb* /dev/video* /dev/input* 2>/dev/null || true",
    }

    meta = {"host": args.host, "timestamp": now(), "results": {}}
    for key, cmd in commands.items():
        info(f"📋 Gathering {key} ...")
        r = run(ssh_cmd(args.host, args.user, args.port, args.password, cmd))
        meta["results"][key] = safe_decode(r.stdout or b"").strip()

    # Save all data to a single metadata.json file
    meta_file = STATE_DIR / "metadata.json"
    with open(meta_file, "w") as f:
        json.dump(meta, f, indent=2)

    info(f"✅ Metadata collected → {meta_file}")
    return meta

# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Fetch metadata from printer via SSH (no binaries).")
    parser.add_argument("--host", required=True, help="Printer IP address")
    parser.add_argument("--user", required=True, help="SSH username (usually root)")
    parser.add_argument("--password", required=True, help="SSH password")
    parser.add_argument("--port", type=int, default=22, help="SSH port (default 22)")
    args = parser.parse_args()

    info(f"🔌 Connecting to {args.user}@{args.host}:{args.port} …")

    # Verify connectivity first
    test_cmd = ssh_cmd(args.host, args.user, args.port, args.password, "echo connected")
    r = run(test_cmd)
    output = safe_decode(r.stdout)
    if "connected" not in output.lower():
        err("SSH connection failed. Check credentials or network.")
        sys.exit(2)

    info("✅ SSH connection verified.")
    meta = collect_metadata(args)

    # Record success checkpoint
    save_checkpoint(stage="fetch_metadata_complete", meta={"status": "ok", "host": args.host})
    info("🎉 Metadata-only fetch completed successfully.")
    return 0

# ---------------------------------------------------------------------
if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        err("Interrupted by user.")
        sys.exit(130)
