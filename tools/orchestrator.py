#!/usr/bin/env python3
# ==========================================================
# K2Rebuild - orchestrator.py
# Unified firmware build coordinator with auto-fetch
# ==========================================================
import os, sys, json, subprocess, time
from datetime import datetime
from pathlib import Path

TOOLS_DIR = Path("/tools")
OUTPUT_DIR = Path("/repo/output")
CHECKPOINT = OUTPUT_DIR / "checkpoint.json"
DEVICE_STATE = OUTPUT_DIR / "device_state"
EXTRACTED = OUTPUT_DIR / "extracted" / "_latest_firmware.img.extracted"

def log(msg, level="INFO"):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [{level}] {msg}", flush=True)

def checkpoint(stage):
    data = {"stage": stage, "ts": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}
    CHECKPOINT.write_text(json.dumps(data, indent=2))
    log(f"🧩 Checkpoint updated → {stage}")

def read_checkpoint():
    if CHECKPOINT.exists():
        try:
            return json.load(open(CHECKPOINT)).get("stage", "none")
        except Exception:
            return "none"
    return "none"

def ensure_firmware_present():
    """Ensure rootfs and firmware image exist, else trigger generate_fw.py automatically"""
    img_path = EXTRACTED / "_latest_firmware.img"
    rootfs_dir = next(EXTRACTED.rglob("rootfs"), None)

    if img_path.exists() and rootfs_dir and rootfs_dir.is_dir():
        log("✅ Firmware image and rootfs already available.")
        return True

    log("⚠️ Firmware image or rootfs missing — invoking generate_fw.py …", "WARN")
    try:
        subprocess.check_call(["python3", str(TOOLS_DIR / "generate_fw.py")])
        rootfs_dir = next(EXTRACTED.rglob("rootfs"), None)
        if not rootfs_dir or not rootfs_dir.is_dir():
            log("❌ Firmware generation failed — rootfs not found.", "ERROR")
            sys.exit(1)
        log("✅ Firmware successfully fetched and extracted.")
        return True
    except subprocess.CalledProcessError as e:
        log(f"❌ generate_fw.py failed with exit code {e.returncode}", "ERROR")
        sys.exit(e.returncode)

def run_stage(script_name):
    path = TOOLS_DIR / f"{script_name}.py"
    if not path.exists():
        log(f"❌ Missing tool script: {script_name}.py", "ERROR")
        sys.exit(1)
    log(f"▶️ Running stage: {script_name}")
    try:
        subprocess.check_call(["python3", str(path)])
        log(f"✅ Stage '{script_name}' complete")
    except subprocess.CalledProcessError as e:
        log(f"❌ Stage '{script_name}' failed with exit code {e.returncode}", "ERROR")
        sys.exit(e.returncode)

def main():
    if len(sys.argv) < 2:
        print("Usage: orchestrator.py [build|fetch]")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    log(f"▶️ Mode: {cmd}")

    if cmd == "fetch":
        # Delegate directly to fetch_device_state.py
        log("📡 Launching fetch_device_state.py (SSH metadata fetch)…")
        fetch = TOOLS_DIR / "fetch_device_state.py"
        if not fetch.exists():
            log("❌ Missing fetch_device_state.py!", "ERROR")
            sys.exit(1)
        subprocess.check_call(["python3", str(fetch)] + sys.argv[2:])
        checkpoint("fetch_metadata_complete")
        sys.exit(0)

    elif cmd == "build":
        stage = read_checkpoint()
        log(f"🧩 Current stage: {stage}")

        # Ensure firmware exists (auto-fetch if missing)
        ensure_firmware_present()

        # Define pipeline stages in order
        stages = [
            "detect_rootfs",
            "unsquash",
            "inject_upstream",
            "repack_fw",
            "validate_fw",
        ]

        start_idx = 0
        if stage != "none":
            for i, s in enumerate(stages):
                if stage in s:
                    start_idx = i + 1
                    break

        for s in stages[start_idx:]:
            run_stage(s)
            checkpoint(f"{s}_complete")

        log("🎉 Firmware build pipeline completed successfully.")
        sys.exit(0)

    else:
        print("Usage: orchestrator.py [build|fetch]")
        sys.exit(1)

if __name__ == "__main__":
    main()
