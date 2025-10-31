#!/usr/bin/env python3
# validate_fw.py — verify that rebuilt components match policy

import os, json, sys, hashlib
from typing import Dict
from checkpoint import stage_done
from progress import update_progress

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/repo/output")
WORK_DIR   = os.path.join(OUTPUT_DIR, "work")

REQUIRED = {
    "rootfs": os.path.join(WORK_DIR, "rootfs.squashfs"),
    "sw-description": os.path.join(WORK_DIR, "sw-description"),
}
OPTIONAL = {
    "uboot": os.path.join(WORK_DIR, "uboot"),     # allowed missing if printer-specific
    "kernel": os.path.join(WORK_DIR, "kernel"),   # allowed missing if printer-specific
}

def sha256sum(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def verify_component(name: str, path: str) -> Dict[str, str]:
    if not os.path.exists(path):
        return {"status": "missing", "sha256": "-"}
    if os.path.isdir(path):
        return {"status": "error", "sha256": "-", "error": "is directory"}
    return {"status": "ok", "sha256": sha256sum(path)}

def main():
    update_progress("validate_fw", "Starting firmware validation …", status="info")
    results = {}

    # Required first
    missing = []
    for n, p in REQUIRED.items():
        r = verify_component(n, p)
        results[n] = r
        if r["status"] != "ok":
            missing.append(n)

    # Optional after
    for n, p in OPTIONAL.items():
        r = verify_component(n, p)
        results[n] = r

    # Render a quick summary to file
    summary_path = os.path.join(OUTPUT_DIR, "rebuilt_validation_report.json")
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)

    if missing:
        update_progress("validate_fw", f"Missing required: {', '.join(missing)}", status="error", extra=results)
        stage_done("validate_failed", missing=missing, results=results)
        print("Validation failed:", ", ".join(missing))
        sys.exit(1)

    update_progress("validate_fw", "All required components OK", status="ok", extra=results)
    stage_done("validate_fw", results=results)

if __name__ == "__main__":
    main()
