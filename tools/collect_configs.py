#!/usr/bin/env python3
"""
Collect Creality printer configuration, macros, and UI assets from the extracted rootfs.

Run automatically during build stage after unsquash.
"""

import os, json, shutil
from pathlib import Path

ROOTFS = Path("/repo/output/work/rootfs")
OUT = Path("/repo/output/extracted_configs")
OUT.mkdir(parents=True, exist_ok=True)

patterns = {
    "printer_cfg": ["**/printer*.cfg"],
    "creality_cfg": [
        "**/usr/share/klipper*/config/*",
        "**/etc/klipper*/config*",
    ],
    "macros": ["**/*macro*.cfg", "**/*macros*.cfg"],
    "filament_related": ["**/*filament*", "**/*cfs*"],
    "qml_ui": ["**/*.qml", "**/*.js", "**/qml/*"],
    "services": ["**/systemd/system/*creality*.service"],
}

def safe_copy(src):
    rel = src.relative_to(ROOTFS)
    dest = OUT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(src, dest)
        return True
    except Exception:
        return False

results = {}

print(f"[collect_configs] Searching in {ROOTFS}")

for category, globs in patterns.items():
    found = []
    for g in globs:
        for p in ROOTFS.glob(g):
            if p.is_file():
                found.append(str(p))
                safe_copy(p)
    results[category] = found
    print(f"[collect_configs] {category}: {len(found)} found")

# Save summary
with open(OUT / "report.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print("[collect_configs] ✅ Done")
print(f"[collect_configs] Output copied to: {OUT}")
print(f"[collect_configs] Summary written to: {OUT}/report.json")
