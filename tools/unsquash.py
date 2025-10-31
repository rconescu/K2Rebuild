#!/usr/bin/env python3
import os, sys
from colorama import Fore, Style
from utils import run, ensure_dir
from progress import update_progress
from checkpoint import get_checkpoint, stage_done

OUT_DIR = os.environ.get("OUT_DIR", "/repo/output")
WORK_DIR = os.path.join(OUT_DIR, "work")
ROOTFS_WORK = os.path.join(WORK_DIR, "rootfs")
ROOTFS_SQUASH = os.path.join(WORK_DIR, "rootfs.squashfs")

def main():
    ck = get_checkpoint()
    src = ck.get("artifacts", {}).get("rootfs_source")
    if not src or not os.path.exists(src):
        print(f"{Fore.RED}[unsquash] ❌ checkpoint missing rootfs_source. Run detect_rootfs first.{Style.RESET_ALL}")
        sys.exit(1)

    ensure_dir(ROOTFS_WORK)
    print(f"{Fore.CYAN}[unsquash]{Style.RESET_ALL} Extracting squashfs from source dir → {ROOTFS_WORK}")

    # If the source is already a directory tree, pack to squash then unsquash for normalization
    # 1) Create temporary squashfs from src
    tmp_squash = ROOTFS_SQUASH
    run(["mksquashfs", src, tmp_squash, "-comp", "xz", "-noappend"])
    # 2) Unsquash into work tree
    run(["unsquashfs", "-f", "-d", ROOTFS_WORK, tmp_squash])

    update_progress("unsquash", f"Extracted filesystem into {ROOTFS_WORK}")
    stage_done("unsquash", rootfs_dir=ROOTFS_WORK, rootfs_squash=ROOTFS_SQUASH)

if __name__ == "__main__":
    main()
