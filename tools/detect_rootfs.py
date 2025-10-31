#!/usr/bin/env python3
# ==========================================================
# K2Rebuild - detect_rootfs.py
# Verifies and normalizes extracted rootfs
# ==========================================================
import os, sys, json
from pathlib import Path
from datetime import datetime

OUTPUT = Path("/repo/output")
EXTRACTED = OUTPUT / "extracted" / "_latest_firmware.img.extracted"
CHECKPOINT = OUTPUT / "checkpoint.json"

def log(msg):
    print(f"[detect_rootfs] {msg}", flush=True)

def write_checkpoint(stage):
    CHECKPOINT.write_text(json.dumps({"stage": stage, "ts": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}, indent=2))

def main():
    log(f"Looking for extracted rootfs at: {EXTRACTED}")
    if not EXTRACTED.exists():
        log("❌ No extracted firmware found. Run generate_fw first.")
        sys.exit(1)

    rootfs = next(EXTRACTED.rglob("rootfs"), None)
    if not rootfs:
        log("❌ rootfs directory not found after extraction.")
        sys.exit(1)

    log(f"✅ Found rootfs at {rootfs}")
    write_checkpoint("detect_rootfs_complete")

if __name__ == "__main__":
    main()
