#!/usr/bin/env python3
import os, sys, subprocess, json
from colorama import Fore, Style
from utils import run, ensure_dir, write_text
from progress import update_progress
from checkpoint import get_checkpoint, stage_done

OUT_DIR = os.environ.get("OUT_DIR", "/repo/output")
WORK_DIR = os.path.join(OUT_DIR, "work")
ROOTFS_DIR = os.path.join(WORK_DIR, "rootfs")
UPSTREAM_DIR = os.path.join(WORK_DIR, "upstream")

REPOS = {
    "klipper":   "https://github.com/Klipper3d/klipper.git",
    "moonraker": "https://github.com/Arksine/moonraker.git",
    "mainsail":  "https://github.com/mainsail-crew/mainsail.git",
}

def ensure_repo(name, url, dest):
    if not os.path.exists(dest):
        run(["git", "clone", "--depth", "1", url, dest])
    else:
        run(["git", "fetch", "--all"], cwd=dest)
        run(["git", "reset", "--hard", "origin/master"], cwd=dest)

def main():
    ck = get_checkpoint()
    rootfs = ck.get("artifacts", {}).get("rootfs_dir")
    if not rootfs or not os.path.isdir(rootfs):
        print(f"{Fore.RED}[inject_upstream] ❌ Missing rootfs_dir. Run unsquash first.{Style.RESET_ALL}")
        sys.exit(1)

    ensure_dir(UPSTREAM_DIR)
    print(f"{Fore.CYAN}[inject_upstream]{Style.RESET_ALL} Cloning / updating upstream projects …")
    for name, url in REPOS.items():
        ensure_repo(name, url, os.path.join(UPSTREAM_DIR, name))

    # Example: copy Mainsail web UI into the image
    target_www = os.path.join(rootfs, "usr/share/mainsail")
    ensure_dir(target_www)
    run(["rsync", "-a", "--delete", os.path.join(UPSTREAM_DIR, "mainsail/"), target_www])

    # Drop a marker config
    write_text(os.path.join(rootfs, "etc/k2rebuild.conf"), "K2REBUILD_INJECTED=1\n")

    # Save choice
    ui_choice = {"ui": "mainsail"}
    ensure_dir(OUT_DIR)
    with open(os.path.join(OUT_DIR, "ui_choice.json"), "w") as f:
        json.dump(ui_choice, f, indent=2)

    update_progress("inject_upstream", "Upstream components injected (Mainsail UI + marker).")
    stage_done("inject_upstream")

if __name__ == "__main__":
    main()
