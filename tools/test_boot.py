#!/usr/bin/env python3
import os, sys, subprocess, time
from checkpoint import get_checkpoint, update_checkpoint, stage_done, write_error

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/repo/output")
WORK_DIR   = os.path.join(OUTPUT_DIR, "work")
LOG_PATH   = os.path.join(OUTPUT_DIR, "qemu_boot.log")
QEMU_BIN   = "/usr/bin/qemu-system-arm"

def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 🧠 {msg}", flush=True)

def find_component(name):
    path = os.path.join(WORK_DIR, name)
    if os.path.exists(path):
        return path
    alt = os.path.join(OUTPUT_DIR, name)
    if os.path.exists(alt):
        return alt
    return None

def main():
    log("Starting QEMU test boot environment…")
    kernel = find_component("kernel")
    rootfs = find_component("rootfs.squashfs") or find_component("rootfs")
    dtb    = find_component("sun8iw20p1.dtb")

    if not kernel or not rootfs:
        write_error("Missing kernel or rootfs for QEMU test")
        sys.exit("❌ Cannot boot: kernel or rootfs missing")

    if not os.path.exists(QEMU_BIN):
        write_error("QEMU not installed in container")
        sys.exit("❌ qemu-system-arm binary not found")

    # Build qemu command for Allwinner T113 (ARMv7)
    qemu_cmd = [
        QEMU_BIN,
        "-M", "virt",
        "-cpu", "cortex-a7",
        "-m", "512M",
        "-nographic",
        "-kernel", kernel,
        "-append", "console=ttyAMA0 root=/dev/ram rdinit=/sbin/init loglevel=3",
        "-drive", f"file={rootfs},if=none,format=raw,id=fs",
        "-device", "virtio-blk-device,drive=fs",
    ]
    if dtb:
        qemu_cmd += ["-dtb", dtb]

    log("Launching QEMU …")
    log(f"Command: {' '.join(qemu_cmd)}")

    with open(LOG_PATH, "w") as f:
        proc = subprocess.Popen(qemu_cmd, stdout=f, stderr=subprocess.STDOUT)

    # wait ~30 seconds for kernel + init sequence
    time.sleep(30)
    proc.terminate()
    time.sleep(3)

    if proc.poll() is None:
        proc.kill()
    log("🧾 QEMU run complete; log captured.")
    update_checkpoint({"qemu_log": LOG_PATH})
    stage_done("test_boot", qemu_log=LOG_PATH)
    log(f"✅ Log saved: {LOG_PATH}")

if __name__ == "__main__":
    main()
