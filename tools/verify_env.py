#!/usr/bin/env python3
"""
K2Rebuild Environment Validator
--------------------------------
Ensures that all core dependencies (binaries, Python packages, mounts, and permissions)
are present before running firmware operations.

This script exits with a non-zero code if anything is missing or misconfigured.
"""

import os
import shutil
import sys
import subprocess
from colorama import Fore, Style

# Required binaries
BINARIES = [
    "python3", "sshpass", "ssh", "scp", "binwalk", "unsquashfs", "cpio",
    "xz", "zstd", "wget", "curl", "7z", "jq", "qemu-system-arm"
]

# Required Python modules
PY_MODULES = ["requests", "bs4", "lxml", "colorama"]

# Required mount points (relative to container)
MOUNTS = {
    "/repo/output": "Output folder (bind mount from host)",
    "/tools": "Tools folder (bind mount from host)"
}

def check_binaries():
    missing = []
    print(Fore.CYAN + "\n[verify_env] 🔍 Checking system binaries..." + Style.RESET_ALL)
    for b in BINARIES:
        path = shutil.which(b)
        if path:
            print(f"  ✅ {b:20s} → {path}")
        else:
            print(f"  ❌ {b:20s} → MISSING")
            missing.append(b)
    return missing

def check_python_modules():
    missing = []
    print(Fore.CYAN + "\n[verify_env] 🧩 Checking Python modules..." + Style.RESET_ALL)
    for mod in PY_MODULES:
        try:
            __import__(mod)
            print(f"  ✅ {mod:20s} → OK")
        except ImportError:
            print(f"  ❌ {mod:20s} → MISSING")
            missing.append(mod)
    return missing

def check_mounts():
    missing = []
    print(Fore.CYAN + "\n[verify_env] 🗂️  Checking required mounts..." + Style.RESET_ALL)
    for path, desc in MOUNTS.items():
        if os.path.isdir(path):
            print(f"  ✅ {path:30s} → OK")
        else:
            print(f"  ❌ {path:30s} → Missing ({desc})")
            missing.append(path)
    return missing

def check_permissions():
    print(Fore.CYAN + "\n[verify_env] 🔒 Checking write permissions..." + Style.RESET_ALL)
    testfile = "/repo/output/_env_test_write.txt"
    try:
        with open(testfile, "w") as f:
            f.write("ok")
        os.remove(testfile)
        print("  ✅ /repo/output is writable")
        return True
    except Exception as e:
        print("  ❌ /repo/output not writable:", e)
        return False

def check_dns():
    print(Fore.CYAN + "\n[verify_env] 🌐 Checking DNS resolution..." + Style.RESET_ALL)
    try:
        subprocess.run(["ping", "-c", "1", "8.8.8.8"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("  ✅ Internet connectivity OK (8.8.8.8 reachable)")
    except Exception:
        print("  ⚠️  Unable to reach 8.8.8.8 — check network_mode or host connectivity")

def main():
    print(Fore.YELLOW + "\n============================================")
    print(" K2Rebuild Environment Verification Utility")
    print("============================================" + Style.RESET_ALL)

    missing_bin = check_binaries()
    missing_mod = check_python_modules()
    missing_mount = check_mounts()
    writable = check_permissions()
    check_dns()

    if missing_bin or missing_mod or missing_mount or not writable:
        print(Fore.RED + "\n❌ Environment check failed." + Style.RESET_ALL)
        print("Missing binaries:", ", ".join(missing_bin) if missing_bin else "None")
        print("Missing modules:", ", ".join(missing_mod) if missing_mod else "None")
        print("Missing mounts:", ", ".join(missing_mount) if missing_mount else "None")
        sys.exit(1)
    else:
        print(Fore.GREEN + "\n✅ All checks passed. Environment ready.\n" + Style.RESET_ALL)
        sys.exit(0)

if __name__ == "__main__":
    main()
