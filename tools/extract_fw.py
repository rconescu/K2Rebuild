#!/usr/bin/env python3
import subprocess
from pathlib import Path
import shutil
from tools.logger import log
from tools.checkpoint import stage_done, update_checkpoint

OUTPUT_DIR  = Path("/repo/output")
FW_IMG      = OUTPUT_DIR / "latest_firmware.img"
EXTRACT_DIR = OUTPUT_DIR / "extracted"
MARK = EXTRACT_DIR / "_latest_firmware.img.extracted"

def main():
    log("🧩 Running binwalk extraction (as root)…")

    # ✅ Ensure clean extraction directory
    if EXTRACT_DIR.exists():
        shutil.rmtree(EXTRACT_DIR)
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)

    # ✅ Run binwalk inside EXTRACT_DIR
    subprocess.check_call([
        "bash", "-c",
        f"cd {EXTRACT_DIR} && binwalk --run-as=root -e {FW_IMG}"
    ])

    # ✅ Verify extraction target exists
    if not MARK.exists():
        raise SystemExit("❌ Extraction failed — missing extracted directory")

    log("✅ Extraction done")

    # ✅ Mark stage complete
    stage_done("extracted")

    # ✅ Save metadata
    update_checkpoint({"extracted": str(MARK)})

if __name__ == "__main__":
    main()
