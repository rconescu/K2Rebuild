#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QEMU boot smoke-test for rebuilt firmware.

Goal:
  - Try to boot the extracted kernel under QEMU headless
  - Capture serial output and detect early boot banners
  - Write a qemu_test_report.json with status/pass/fail/skip, reasons, and log path
  - Update checkpoint to 'qemu_test' (and 'qemu_test_passed' if success)

This is a *best-effort* smoke test. Allwinner T113/SUN8I boards are not fully
emulated upstream; we therefore:
  - Prefer a simple "kernel banner appears" criteria as PASS
  - If kernel/DTB/QEMU missing → SKIP (don’t fail the build)
  - If STRICT mode on → treat SKIP/FAIL as hard failure

Env controls:
  QEMU_TEST_ENABLE=1/0      : enable/disable stage (default 1)
  QEMU_TEST_TIMEOUT=seconds : per-run timeout (default 25)
  QEMU_TEST_STRICT=1/0      : if 1, any skip/fail exits nonzero
  QEMU_MACHINE=<qemu -M>    : override machine (default: virt)
  QEMU_BIN=<path>           : override qemu-system-arm (default: auto-discover)

Inputs (typical):
  - Kernel:   /repo/output/extracted/.../cpio-root/kernel OR /repo/output/work/kernel
  - Rootfs:   /repo/output/work/rootfs.squashfs (not mounted, just present)
  - DTB(s):   *.dtb if any found (optional; not required for 'virt' machine)

Outputs:
  - /repo/output/qemu_boot.log
  - /repo/output/qemu_test_report.json
  - checkpoint.json stage update
"""
import json, os, re, shutil, subprocess, sys, time
from pathlib import Path

# ---------- small local checkpoint helpers (compatible with your existing ones) ----------
OUT_DIR = Path(os.environ.get("OUT_DIR", "/repo/output")).resolve()
STATE_DIR = OUT_DIR
CHECKPOINT_JSON = STATE_DIR / "checkpoint.json"
PROGRESS_JSON = STATE_DIR / "progress.json"

def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def load_checkpoint():
    if CHECKPOINT_JSON.exists():
        with open(CHECKPOINT_JSON, "r") as f:
            return json.load(f)
    return {"stage": "none", "meta": {}}

def save_checkpoint(stage=None, **meta):
    data = load_checkpoint()
    if stage:
        data["stage"] = stage
    if "meta" not in data: data["meta"] = {}
    data["meta"].update(meta)
    with open(CHECKPOINT_JSON, "w") as f:
        json.dump(data, f, indent=2)
    # also append to progress.json for human-friendly timeline
    line = {
        "ts": _now(),
        "stage": stage or data.get("stage"),
        "meta": meta,
    }
    with open(PROGRESS_JSON, "a") as f:
        f.write(json.dumps(line) + "\n")

# ---------- util ----------
def info(msg):  print(f"[{_now()}] [INFO] {msg}")
def warn(msg):  print(f"[{_now()}] [WARN] {msg}")
def err(msg):   print(f"[{_now()}] [ERROR] {msg}", file=sys.stderr)

def which(cmd):
    p = shutil.which(cmd)
    return p

def write_json(path: Path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)

# ---------- discovery ----------
def find_kernel():
    # prefer already extracted kernel in work or extracted tree
    candidates = [
        OUT_DIR / "work" / "kernel",
        OUT_DIR / "extracted" / "_latest_firmware.img.extracted" / "cpio-root" / "kernel",
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            return p
    # sometimes kernel is named 'Image', 'zImage', 'uImage' under cpio-root/boot/
    alt_globs = [
        OUT_DIR / "work" / "**" / "zImage",
        OUT_DIR / "work" / "**" / "uImage",
        OUT_DIR / "work" / "**" / "Image",
        OUT_DIR / "extracted" / "_latest_firmware.img.extracted" / "cpio-root" / "boot" / "*Image*",
    ]
    for g in alt_globs:
        for p in g.parent.glob(g.name):
            if p.is_file():
                return p
    return None

def find_dtb():
    # optional; if present we'll pass -dtb to QEMU (not strictly required for -M virt)
    roots = [
        OUT_DIR / "work",
        OUT_DIR / "extracted" / "_latest_firmware.img.extracted" / "cpio-root",
    ]
    for r in roots:
        if not r.exists(): continue
        for p in r.rglob("*.dtb"):
            if p.is_file():
                return p
    return None

def find_rootfs():
    # presence only (we don't mount it in QEMU 'virt' test)
    p = OUT_DIR / "work" / "rootfs.squashfs"
    return p if p.exists() and p.is_file() else None

# ---------- qemu run ----------
BOOT_OK_PATTERNS = [
    re.compile(r"Linux version", re.I),
    re.compile(r"Booting Linux", re.I),
    re.compile(r"Starting kernel", re.I),
]

def run_qemu(kernel: Path, dtb: Path|None, timeout_s: int, machine: str, qemu_bin: str, log_path: Path):
    cmd = [
        qemu_bin,
        "-M", machine,
        "-m", "512M",
        "-nographic",
        "-serial", "stdio",
        "-kernel", str(kernel),
        "-append", "console=ttyAMA0 panic=1 loglevel=7",
    ]
    if dtb and machine != "virt":  # dtb only when a board model actually expects one
        cmd.extend(["-dtb", str(dtb)])

    info(f"Spawning QEMU: {' '.join(cmd)}")
    with open(log_path, "wb") as logf:
        try:
            p = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT)
        except FileNotFoundError:
            return {"status": "error", "reason": f"qemu binary not found: {qemu_bin}"}
        except Exception as e:
            return {"status": "error", "reason": f"spawn failed: {e!r}"}

        # Wait up to timeout while tailing the file looking for boot banners
        start = time.time()
        last_size = 0
        matched = False
        while True:
            time.sleep(0.5)
            # read tail incrementally
            try:
                with open(log_path, "rb") as rf:
                    rf.seek(last_size)
                    chunk = rf.read().decode("utf-8", errors="ignore")
                    if chunk:
                        # quick scan for success patterns
                        for pat in BOOT_OK_PATTERNS:
                            if pat.search(chunk):
                                matched = True
                                break
                        last_size = rf.tell()
            except Exception:
                pass

            if matched:
                # give kernel a moment more, then stop
                time.sleep(1.0)
                p.terminate()
                try:
                    p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    p.kill()
                return {"status": "passed", "reason": "kernel banner detected"}

            if (time.time() - start) > timeout_s:
                # timeout → stop qemu
                try:
                    p.terminate()
                    p.wait(timeout=2)
                except Exception:
                    try: p.kill()
                    except Exception: pass
                break

        # On timeout, judge by whether *any* output came out
        had_output = log_path.exists() and log_path.stat().st_size > 0
        return {"status": "failed" if had_output else "failed_no_output",
                "reason": "timeout waiting for kernel banner"}

# ---------- main ----------
def main():
    enable = os.environ.get("QEMU_TEST_ENABLE", "1") != "0"
    strict = os.environ.get("QEMU_TEST_STRICT", "0") == "1"
    timeout_s = int(os.environ.get("QEMU_TEST_TIMEOUT", "25"))
    machine = os.environ.get("QEMU_MACHINE", "virt")  # safest generic
    qemu_bin = os.environ.get("QEMU_BIN", "") or which("qemu-system-arm") or ""

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    log_path = OUT_DIR / "qemu_boot.log"
    report_path = OUT_DIR / "qemu_test_report.json"

    save_checkpoint(stage="qemu_test", meta={"enable": enable, "strict": strict})

    if not enable:
        warn("QEMU_TEST_ENABLE=0 → skipping emulation stage")
        write_json(report_path, {"status": "skipped", "reason": "disabled"})
        return 0

    if not qemu_bin:
        warn("qemu-system-arm not found in PATH → skipping")
        write_json(report_path, {"status": "skipped", "reason": "qemu not installed"})
        return 0 if not strict else 2

    kernel = find_kernel()
    if not kernel:
        warn("No kernel image found → skipping QEMU test")
        write_json(report_path, {"status": "skipped", "reason": "kernel not found"})
        return 0 if not strict else 2

    dtb = find_dtb()
    if dtb:
        info(f"Found DTB: {dtb}")
    else:
        info("No DTB found (ok for -M virt).")

    rootfs = find_rootfs()
    if rootfs:
        info(f"Found rootfs: {rootfs}")
    else:
        info("rootfs.squashfs not found (not required for banner check).")

    info(f"QEMU machine: {machine}")
    info(f"Timeout: {timeout_s}s")
    if log_path.exists():
        try: log_path.unlink()
        except Exception: pass

    result = run_qemu(kernel, dtb, timeout_s, machine, qemu_bin, log_path)
    status = result.get("status", "error")
    reason = result.get("reason", "")
    info(f"QEMU test result: {status} ({reason})")

    write_json(report_path, {
        "status": status,
        "reason": reason,
        "kernel": str(kernel),
        "dtb": str(dtb) if dtb else None,
        "machine": machine,
        "timeout": timeout_s,
        "log": str(log_path),
        "ts": _now(),
    })

    if status == "passed":
        save_checkpoint(stage="qemu_test_passed")
        return 0

    # failed / skipped
    save_checkpoint(stage="qemu_test_done", meta={"status": status, "reason": reason})
    if strict and status != "passed":
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
