#!/usr/bin/env python3
# =============================================================================
#  K2Rebuild Firmware Image Generator — Full Production Build
# =============================================================================
import os
import sys
import re
import hashlib
import subprocess
import json
import requests
from bs4 import BeautifulSoup
from colorama import Fore, Style, init

init(autoreset=True)

# -------------------------------------------------------------------------
# Logging Helpers
# -------------------------------------------------------------------------
def log_info(msg):    print(f"{Fore.CYAN}[generate_fw] [INFO] {msg}{Style.RESET_ALL}")
def log_warn(msg):    print(f"{Fore.YELLOW}[generate_fw] [WARN] {msg}{Style.RESET_ALL}")
def log_error(msg):   print(f"{Fore.RED}[generate_fw] [ERROR] {msg}{Style.RESET_ALL}")
def log_success(msg): print(f"{Fore.GREEN}[generate_fw] [SUCCESS] {msg}{Style.RESET_ALL}")

# -------------------------------------------------------------------------
# Utilities
# -------------------------------------------------------------------------
def sha256sum(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def run(cmd, cwd=None, capture=True):
    if capture:
        result = subprocess.run(cmd, cwd=cwd, shell=False,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    else:
        result = subprocess.run(cmd, cwd=cwd, shell=False)
    return result

# -------------------------------------------------------------------------
# Detect latest firmware link
# -------------------------------------------------------------------------
def detect_latest_firmware_url():
    fw_page = "https://www.creality.com/download/creality-k2-plus-cfs-combo"
    log_info(f"🌐 Checking Creality firmware page: {fw_page}")
    try:
        r = requests.get(fw_page, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        link = soup.find("a", href=re.compile(r"\.img$", re.I))
        if link and link["href"].startswith("http"):
            return link["href"]
    except Exception as e:
        log_warn(f"Failed to fetch firmware page: {e}")
    # fallback — verified mirror
    return "https://file2-cdn.creality.com/file/0be5c59fef5b8640712d8213a0ed1cc2/CR0CN240110C10_ota_img_V1.1.2.10.img"

# -------------------------------------------------------------------------
# Extraction Logic — handles SquashFS, ext4, and nested CPIO containers
# -------------------------------------------------------------------------
def try_extract_rootfs(img_path, extract_dir, output_dir):
    log_info("🧯 Unsquashing rootfs (SquashFS)…")
    unsquash_out = os.path.join(extract_dir, "rootfs")
    os.makedirs(unsquash_out, exist_ok=True)
    result = subprocess.run(["unsquashfs", "-d", unsquash_out, img_path],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stderr = result.stderr.strip()
    stdout = result.stdout.strip()

    if result.returncode == 0:
        log_info("✅ SquashFS extraction successful.")
        return True

    if "Operation not permitted" in stderr and re.search(r"created\s+\d+\s+files", stdout):
        log_warn("unsquashfs reported permission warnings but extraction succeeded.")
        return True

    # Fallback: Detect CPIO block layout
    log_warn("unsquashfs failed; analyzing nested rootfs block…")
    try:
        bw_out = subprocess.check_output(["binwalk", "--quiet", "--term", img_path], text=True)
    except Exception as e:
        log_error(f"binwalk analysis failed: {e}")
        bw_out = ""

    rootfs_offset = None
    for line in bw_out.splitlines():
        if "rootfs" in line.lower():
            parts = line.strip().split()
            if parts and parts[0].isdigit():
                rootfs_offset = int(parts[0])
                break

    # NEW PATCH — fallback for CPIO-based Creality OTA bundles
    if rootfs_offset is None:
        log_warn("No binary offsets found — checking for concatenated CPIO members…")
        try:
            cpio_dir = os.path.join(extract_dir, "cpio-root")
            os.makedirs(cpio_dir, exist_ok=True)
            subprocess.run(
                ["bash", "-c", f"cd '{cpio_dir}' && cpio -idmv < '{img_path}'"],
                check=False,
            )
            if os.path.exists(os.path.join(cpio_dir, "rootfs")):
                log_info("✅ Extracted CPIO container successfully.")
                rootfs_file = os.path.join(cpio_dir, "rootfs")
            else:
                log_error("❌ Could not locate 'rootfs' inside CPIO archive.")
                return False
        except Exception as e:
            log_error(f"CPIO pass failed: {e}")
            return False
    else:
        # Normal binary offset mode
        rootfs_file = os.path.join(output_dir, "work", "rootfs.img")
        try:
            dd_cmd = ["dd", f"if={img_path}", f"of={rootfs_file}", f"bs=1", f"skip={rootfs_offset}"]
            subprocess.run(dd_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            log_error(f"dd failed: {e}")
            return False

    # Inspect rootfs file
    file_type = subprocess.check_output(["file", "-b", rootfs_file], text=True).strip()
    log_info(f"🔍 rootfs.img detected type: {file_type}")

    if "Squashfs" in file_type:
        log_info("🧯 Unsquashing nested SquashFS rootfs.img …")
        res = subprocess.run(["unsquashfs", "-d", unsquash_out, rootfs_file],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return (res.returncode == 0)

    elif "ext4" in file_type.lower():
        log_info("🧩 Mounting ext4 rootfs.img (read-only)…")
        mount_dir = unsquash_out
        os.makedirs(mount_dir, exist_ok=True)
        subprocess.run(["guestmount", "-a", rootfs_file, "-m", "/dev/sda1", "--ro", mount_dir],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return True

    elif "cpio" in file_type.lower():
        log_info("📦 Extracting cpio rootfs.img …")
        cmd = f"cd '{unsquash_out}' && cpio -idmv < '{rootfs_file}'"
        subprocess.run(cmd, shell=True)
        return True

    elif any(x in file_type.lower() for x in ("zstd", "lz4", "xz")):
        log_info("🔓 Decompressing compressed rootfs.img …")
        decomp_cmd = f"zstd -d '{rootfs_file}' -o '{rootfs_file}.dec' || lz4 -d '{rootfs_file}' '{rootfs_file}.dec' || xz -d -c '{rootfs_file}' > '{rootfs_file}.dec'"
        subprocess.run(decomp_cmd, shell=True)
        if os.path.exists(f"{rootfs_file}.dec"):
            log_info("✅ Decompressed successfully.")
            return True

    log_error("❌ Rootfs type unsupported or image corrupt.")
    return False

# -------------------------------------------------------------------------
# Main Routine
# -------------------------------------------------------------------------
def main():
    output_dir = os.environ.get("OUTPUT_DIR", "/repo/output")
    work_dir = os.path.join(output_dir, "work")
    extract_dir = os.path.join(output_dir, "extracted")
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(extract_dir, exist_ok=True)

    log_info("🧮 Starting firmware image generation...")

    # Detect model from device_state metadata
    metadata_file = os.path.join(output_dir, "device_state", "metadata.json")
    model = "creality_k2"
    if os.path.exists(metadata_file):
        with open(metadata_file, "r") as f:
            meta = json.load(f)
        device_model = str(meta.get("results", {}).get("device_model", "")).lower()
        if "k1" in device_model:
            model = "creality_k1"
        elif "k2" in device_model:
            model = "creality_k2"
    log_info(f"🧩 Detected model: {model}")

    # Firmware download
    fw_url = detect_latest_firmware_url()
    fw_name = os.path.basename(fw_url)
    img_path = os.path.join(work_dir, fw_name)
    log_info(f"🌐 Downloading firmware from {fw_url} …")
    try:
        resp = requests.get(fw_url, stream=True, timeout=60)
        resp.raise_for_status()
        with open(img_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        log_info(f"🔽 Downloaded {fw_name} → {img_path}")
    except Exception as e:
        log_error(f"Firmware download failed: {e}")
        sys.exit(1)

    fw_hash = sha256sum(img_path)
    log_info(f"📦 SHA256: {fw_hash}")

    ok = try_extract_rootfs(img_path, extract_dir, output_dir)
    if not ok:
        log_error("❌ Root filesystem extraction failed; aborting.")
        sys.exit(1)

    log_success("✅ Extraction complete.")
    log_success("✅ Firmware retrieval step complete.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(130)
