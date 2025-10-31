#!/usr/bin/env python3
import os, sys, shutil, re
from colorama import Fore, Style
from utils import run, ensure_dir, sha256sum, write_text
from progress import update_progress
from checkpoint import get_checkpoint, stage_done

OUT_DIR = os.environ.get("OUT_DIR", "/repo/output")
WORK_DIR = os.path.join(OUT_DIR, "work")
ROOTFS_DIR = os.path.join(WORK_DIR, "rootfs")
ROOTFS_SQUASH = os.path.join(WORK_DIR, "rootfs.squashfs")
SWDESC = os.path.join(WORK_DIR, "sw-description")
CPIO_MD5 = os.path.join(WORK_DIR, "cpio_item_md5")
FINAL_IMG = os.path.join(OUT_DIR, "custom_firmware.img")

# If kernel/uboot are present from extracted firmware, we keep them
KERNEL_IN = os.path.join(OUT_DIR, "extracted", "_latest_firmware.img.extracted", "kernel")
UBOOT_IN  = os.path.join(OUT_DIR, "extracted", "_latest_firmware.img.extracted", "uboot")

def update_swdesc_for_rootfs(path_desc, rootfs_squash):
    if not os.path.exists(path_desc):
        # minimal sw-description
        write_text(path_desc,
                   "software = {\n  version = \"k2rebuild\";\n  rootfs: file = \"rootfs\"; \n}\n")
    txt = open(path_desc, "r").read()
    # replace size/sha lines for rootfs if they exist; otherwise append
    sha = sha256sum(rootfs_squash)
    size = os.path.getsize(rootfs_squash)
    txt = re.sub(r'(rootfs_sha256\s*=\s*")[0-9a-f]*(")', rf'\1{sha}\2', txt) if "rootfs_sha256" in txt else txt + f'\nrootfs_sha256="{sha}"\n'
    txt = re.sub(r'(rootfs_size\s*=\s*")[0-9]*(")', rf'\1{size}\2', txt) if "rootfs_size" in txt else txt + f'rootfs_size="{size}"\n'
    write_text(path_desc, txt)

def write_cpio_item_md5(out_path, items):
    lines = []
    for name, fpath in items:
        if not os.path.isfile(fpath):
            continue
        lines.append(f"{name}:{sha256sum(fpath)}")
    write_text(out_path, "\n".join(lines) + "\n")

def main():
    ck = get_checkpoint()
    if ck.get("stage") not in ("unsquash", "inject_upstream", "repack_fw"):
        print(f"{Fore.YELLOW}[repack_fw] ℹ️ previous stage: {ck.get('stage')}{Style.RESET_ALL}")

    if not os.path.isdir(ROOTFS_DIR):
        print(f"{Fore.RED}[repack_fw] ❌ Missing {ROOTFS_DIR} — run unsquash/inject first.{Style.RESET_ALL}")
        sys.exit(1)

    print(f"{Fore.CYAN}[repack_fw]{Style.RESET_ALL} Building new squashfs from {ROOTFS_DIR} …")
    run(["mksquashfs", ROOTFS_DIR, ROOTFS_SQUASH, "-comp", "xz", "-noappend"])

    print(f"{Fore.CYAN}[repack_fw]{Style.RESET_ALL} Updating sw-description …")
    update_swdesc_for_rootfs(SWDESC, ROOTFS_SQUASH)

    print(f"{Fore.CYAN}[repack_fw]{Style.RESET_ALL} Regenerating cpio_item_md5 …")
    items = [("rootfs", ROOTFS_SQUASH), ("sw-description", SWDESC)]
    if os.path.isfile(KERNEL_IN): items.append(("kernel", KERNEL_IN))
    if os.path.isfile(UBOOT_IN):  items.append(("uboot", UBOOT_IN))
    write_cpio_item_md5(CPIO_MD5, items)

    # Rebuild SWUpdate CPIO (order matters)
    tmpdir = os.path.join(WORK_DIR, "cpio-build")
    if os.path.isdir(tmpdir): shutil.rmtree(tmpdir)
    ensure_dir(tmpdir)

    # link staged components
    shutil.copy2(SWDESC, os.path.join(tmpdir, "sw-description"))
    shutil.copy2(ROOTFS_SQUASH, os.path.join(tmpdir, "rootfs"))
    if os.path.isfile(KERNEL_IN): shutil.copy2(KERNEL_IN, os.path.join(tmpdir, "kernel"))
    if os.path.isfile(UBOOT_IN):  shutil.copy2(UBOOT_IN,  os.path.join(tmpdir, "uboot"))
    shutil.copy2(CPIO_MD5, os.path.join(tmpdir, "cpio_item_md5"))

    # make CPIO archive
    print(f"{Fore.CYAN}[repack_fw]{Style.RESET_ALL} Creating SWUpdate CPIO …")
    run(["bash", "-lc", f"cd {tmpdir} && find . | cpio -o -H crc > {FINAL_IMG}"])

    print(f"{Fore.GREEN}[repack_fw]{Style.RESET_ALL} ✅ Firmware CPIO ready: {FINAL_IMG}")
    update_progress("repack_fw", f"Firmware repacked: {os.path.basename(FINAL_IMG)}",
                    extra={"rootfs_sha256": sha256sum(ROOTFS_SQUASH), "swdesc": SWDESC})
    stage_done("repack_fw", image=FINAL_IMG, rootfs_squash=ROOTFS_SQUASH, sw_description=SWDESC, cpio_md5=CPIO_MD5)

if __name__ == "__main__":
    main()
