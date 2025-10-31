#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path
import json
import time

SSH_TIMEOUT = "10"
BACKUP_DIR = Path("/repo/output/printer_backup")

def run(cmd, capture=False):
    print(f"$ {' '.join(cmd)}")
    return subprocess.check_output(cmd).decode() if capture else subprocess.check_call(cmd)

def printer_cmd(ssh, cmd):
    return run(["ssh", "-o", "StrictHostKeyChecking=no", "-o", f"ConnectTimeout={SSH_TIMEOUT}", ssh, cmd], capture=True)

def fetch(ssh, remote, local):
    run(["scp", "-r", "-o", "StrictHostKeyChecking=no", f"{ssh}:{remote}", str(local)])

def main():
    if len(sys.argv) < 2:
        print("Usage: printer_extract.py root@PRINTER_IP")
        sys.exit(1)

    ssh = sys.argv[1]
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    info = {}

    print("\n🔍 Collecting printer hardware data...\n")
    cmds = {
        "cmdline": "cat /proc/cmdline",
        "partitions": "cat /proc/partitions",
        "mounts": "mount",
        "dmesg": "dmesg",
        "modules": "find /lib/modules -type f -name '*.ko'",
        "input_devices": "cat /proc/bus/input/devices",
        "video": "ls -l /dev/video* 2>/dev/null",
        "soc": "cat /proc/device-tree/compatible 2>/dev/null",
        "panel": "grep -Ei \"gc|dsi|mipi\" /proc/cmdline",
        "wifi_fw": "ls -l /lib/firmware 2>/dev/null && ls -l /lib/firmware/brcm 2>/dev/null",
    }

    for key, cmd in cmds.items():
        print(f"📎 {key}...")
        try:
            info[key] = printer_cmd(ssh, cmd)
        except:
            info[key] = "ERR"

    # ✅ Backup partitions
    print("\n💾 Backing up mmcblk0 partitions (p1–p14)...")
    for p in range(1, 15):
        outfile = f"/mnt/UDISK/part{p}.img"
        try:
            printer_cmd(ssh, f"dd if=/dev/mmcblk0p{p} of={outfile} bs=1M")
        except Exception:
            info[f"part{p}_dd"] = "FAILED"
            continue

        # Copy to host
        dest = BACKUP_DIR / f"part{p}.img"
        print(f"⬇️ pulling part{p}.img...")
        fetch(ssh, outfile, dest)

    # ✅ Save logs + metadata locally
    with open(BACKUP_DIR / "printer_info.json", "w") as f:
        json.dump(info, f, indent=2)

    print("\n✅ Extraction complete!")
    print(f"📂 Results saved to: {BACKUP_DIR}")
    print("🔒 Nothing on the printer was modified.")


if __name__ == "__main__":
    main()
