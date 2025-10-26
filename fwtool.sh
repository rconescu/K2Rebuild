#!/bin/sh
# k2rebuild-fwtool: helper utility for dissecting and rebuilding Creality K2 firmware images

set -eu
log(){ printf "[k2rebuild] %s\n" "$*"; }

help_text() {
  cat <<'EOF'
K2Rebuild firmware toolkit

Usage: k2rebuild-fwtool <command> [args...]

Commands:
  help                               Show this help
  extract <firmware.bin>             Run binwalk and extract images
  mapparts <image.img>               Mount partitions from an image
  unsquash <rootfs.squashfs>         Unpack squashfs image
  bootstrap-debian <dir> [arch] [rel] Create ARM64 Debian rootfs (default: bookworm)
  build-squashfs <rootdir> <out>     Build squashfs image
  build-ext4 <rootdir> <out> <MB>    Build ext4 image of given size
  make-rootfs-tar <dir> <out.tar.gz> Create compressed tarball
  chroot-run <rootdir> <cmd...>      Chroot into root and execute a command
  get-fw                             Download latest K2 Plus firmware (Python)
  validate <orig_rootfs> <new_rootfs> Run deep validator on both rootfs and compare
EOF
}

extract_firmware(){ IN="$1"; OUT="${IN%.*}.extracted"; mkdir -p "$OUT";
  log "Extracting $IN → $OUT"; binwalk -e "$IN" -C "$OUT" || true;
  find "$OUT" -type f \( -name '*.squashfs' -o -name '*.img' \) -print; }

mapparts(){ IMG="$1"; log "Setting up loop for $IMG";
  LOOP=$(losetup --show -f "$IMG"); log "Loop: $LOOP"; kpartx -av "$LOOP";
  log "Use 'mount /dev/mapper/loop0p1 /mnt' etc."; }

unsquash(){ F="$1"; D="${F%.*}.unsquash"; mkdir -p "$D"; log "Unpacking $F → $D";
  unsquashfs -d "$D" "$F"; log "Done: $D"; }

bootstrap_debian(){ TARGET="$1"; ARCH="${2:-arm64}"; REL="${3:-bookworm}";
  mkdir -p "$TARGET"; log "Bootstrapping Debian $REL ($ARCH)";
  debootstrap --arch="$ARCH" --foreign "$REL" "$TARGET" http://deb.debian.org/debian;
  cp /usr/bin/qemu-aarch64-static "$TARGET/usr/bin/" 2>/dev/null || true;
  chroot "$TARGET" /usr/bin/qemu-aarch64-static /bin/sh -c "/debootstrap/debootstrap --second-stage" || true;
  log "Bootstrap complete in $TARGET"; }

build_squashfs(){ ROOT="$1"; OUT="$2"; log "Building squashfs $OUT"; mksquashfs "$ROOT" "$OUT" -comp xz -b 262144; }
build_ext4(){ ROOT="$1"; OUT="$2"; SIZE="${3:-2048}"; dd if=/dev/zero of="$OUT" bs=1M count="$SIZE" status=none;
  mkfs.ext4 -F "$OUT"; M=/mnt/ext4.$$; mkdir -p "$M"; mount -o loop "$OUT" "$M";
  rsync -aH "$ROOT"/ "$M"; umount "$M"; rmdir "$M"; log "Created ext4 $OUT"; }
make_rootfs_tar(){ DIR="$1"; OUT="$2"; tar -C "$DIR" -czf "$OUT" .; log "Created $OUT"; }
chroot_run(){ ROOT="$1"; shift; cp /etc/resolv.conf "$ROOT/etc/resolv.conf" || true;
  mount -t proc proc "$ROOT/proc" || true; mount -t sysfs sys "$ROOT/sys" || true; mount --rbind /dev "$ROOT/dev" || true;
  chroot "$ROOT" /bin/bash -c "$*"; umount -lf "$ROOT/dev/pts" 2>/dev/null || true; umount -lf "$ROOT/dev" 2>/dev/null || true; umount -lf "$ROOT/sys" 2>/dev/null || true; umount -lf "$ROOT/proc" 2>/dev/null || true; }

get_fw(){ log "Launching firmware downloader..."; /usr/local/bin/download_latest_k2plus_fw; }

validate(){
  ORIG="$1"; NEW="$2"
  if [ ! -d "$ORIG" ] || [ ! -d "$NEW" ]; then
    echo "Usage: k2rebuild-fwtool validate <original_rootfs_dir> <rebuilt_rootfs_dir>"
    exit 1
  fi
  log "Running Python validator on:"
  log "  ORIGINAL: $ORIG"
  log "  REBUILT : $NEW"
  /usr/local/bin/firmware_validator "$ORIG" "$NEW"
  log "Validation complete. See /work/firmware-test-logs/"
}

case "${1:-help}" in
  help) help_text ;;
  extract) extract_firmware "$2" ;;
  mapparts) mapparts "$2" ;;
  unsquash) unsquash "$2" ;;
  bootstrap-debian) bootstrap_debian "$2" "${3:-arm64}" "${4:-bookworm}" ;;
  build-squashfs) build_squashfs "$2" "$3" ;;
  build-ext4) build_ext4 "$2" "$3" "$4" ;;
  make-rootfs-tar) make_rootfs_tar "$2" "$3" ;;
  chroot-run) chroot_run "$2" "${@:3}" ;;
  get-fw) get_fw ;;
  validate) validate "$2" "$3" ;;
  *) help_text ;;
esac
