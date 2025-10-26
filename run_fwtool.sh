#!/usr/bin/env bash
# =============================================================================
# K2Rebuild Orchestrator (Autonomous + Dual Menu)
# -----------------------------------------------------------------------------
# • Automatically ensures the freshest image (pulls/builds silently).
# • Runs all firmware tasks inside the container — no manual execs.
# • Provides:
#     1. SIMPLE MENU: one-click full firmware build/test pipeline.
#     2. ADVANCED MENU: manual control of each step.
# • Removes containers after run, keeps the image cached.
# • All results land in ./output/ on the host.
# =============================================================================

set -Eeuo pipefail
IFS=$'\n\t'

# --- CONFIG ------------------------------------------------------------------
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="$REPO_DIR/output"
COMPOSE_FILE="$REPO_DIR/docker-compose.yml"
SERVICE_NAME="k2rebuild"
IMAGE_REF="${IMAGE_REF:-k2rebuild:latest}"     # can be local or remote tag
IMAGE_MODE="${IMAGE_MODE:-local}"              # "local" or "remote"
SIMPLE_MODE_DEFAULT="1"                        # default to Simple menu
LOG_FILE="$OUTPUT_DIR/host_orchestrator.log"

# --- UTILITIES ---------------------------------------------------------------
timestamp() { date '+%Y-%m-%d %H:%M:%S'; }
log(){ echo -e "[$(timestamp)] $*" | tee -a "$LOG_FILE"; }

have_cmd() { command -v "$1" &>/dev/null; }

choose_compose_cmd() {
  if have_cmd docker && docker compose version &>/dev/null; then
    echo "docker compose"
  elif have_cmd docker-compose; then
    echo "docker-compose"
  else
    echo ""
  fi
}

ensure_compose() {
  local cc
  cc="$(choose_compose_cmd)"
  if [[ -z "$cc" ]]; then
    echo "❌ Docker Compose not found. Install Docker Desktop or docker-compose." >&2
    exit 1
  fi
  echo "$cc"
}

ensure_output_dir() {
  mkdir -p "$OUTPUT_DIR"
  touch "$LOG_FILE"
  if [[ ! -f "$REPO_DIR/.gitignore" ]] || ! grep -qE '^output/?$' "$REPO_DIR/.gitignore"; then
    {
      echo ""
      echo "# Auto-added by run_fwtool.sh"
      echo "output/"
      echo "output/**"
    } >> "$REPO_DIR/.gitignore"
  fi
}

# --- IMAGE MANAGEMENT --------------------------------------------------------
ensure_image_freshness() {
  local cc; cc="$(ensure_compose)"
  log "🧩 Checking image freshness (mode=$IMAGE_MODE, ref=$IMAGE_REF)..."

  if [[ "$IMAGE_MODE" == "remote" ]]; then
    # pull if digest differs
    local local_digest remote_digest
    local_digest="$(docker image inspect "$IMAGE_REF" --format '{{index .RepoDigests 0}}' 2>/dev/null || true)"
    docker pull "$IMAGE_REF" >/dev/null 2>&1 || true
    remote_digest="$(docker image inspect "$IMAGE_REF" --format '{{index .RepoDigests 0}}' 2>/dev/null || true)"
    if [[ "$remote_digest" != "$local_digest" ]]; then
      log "⬇️  Updated image pulled: $IMAGE_REF"
    else
      log "✔️  Image already up-to-date."
    fi
  else
    # local build
    log "🔨 Building local image via compose (refreshing base layers only if newer)…"
    $cc -f "$COMPOSE_FILE" build --pull "$SERVICE_NAME" >/dev/null
    log "✔️  Local image verified fresh."
  fi
}

# --- CORE RUNNER -------------------------------------------------------------
run_in_container() {
  local cc; cc="$(ensure_compose)"
  local args=("$@")
  $cc -f "$COMPOSE_FILE" run --rm "$SERVICE_NAME" "${args[@]}"
}

# --- ACTIONS -----------------------------------------------------------------
action_download_fw() {
  log "Downloading latest K2 Plus firmware..."
  run_in_container get-fw
  log "✅ Firmware downloaded to ./output/firmware/"
}

action_extract_fw() {
  log "Extracting firmware..."
  local img
  img="$(find "$OUTPUT_DIR/firmware" -type f -name '*.img' | sort | tail -n1 || true)"
  if [[ -z "$img" ]]; then log "❌ No .img firmware found in ./output/firmware/"; return 1; fi
  run_in_container extract "/repo/output/firmware/$(basename "$img")"
  log "✅ Extraction complete."
}

action_bootstrap_debian() {
  log "Bootstrapping Debian rootfs..."
  run_in_container bootstrap-debian /repo/output/debian-rootfs arm64 bookworm
  log "✅ Debian rootfs ready."
}

action_validate() {
  log "Running full validation..."
  local orig new
  orig="$(find "$OUTPUT_DIR" -maxdepth 1 -type d -name '*.unsquash' | sort | tail -n1 || true)"
  new="$OUTPUT_DIR/debian-rootfs"
  if [[ -z "$orig" || ! -d "$new" ]]; then
    log "❌ Missing original or rebuilt rootfs."; return 1
  fi
  run_in_container validate "/repo${orig#"$REPO_DIR"}" /repo/output/debian-rootfs
  log "✅ Validation complete. Reports in ./output/firmware-test-logs/"
}

action_package() {
  log "Packaging rebuilt rootfs..."
  local ts out_tgz out_sqfs
  ts="$(date +%Y%m%d-%H%M%S)"
  out_tgz="/repo/output/k2_debian_${ts}.tar.gz"
  out_sqfs="/repo/output/k2_debian_${ts}.squashfs"
  run_in_container make-rootfs-tar /repo/output/debian-rootfs "$out_tgz"
  run_in_container build-squashfs /repo/output/debian-rootfs "$out_sqfs"
  log "✅ Packaged: $(basename "$out_tgz"), $(basename "$out_sqfs")"
}

action_full_pipeline() {
  log "🚀 Starting full firmware build & test pipeline..."
  ensure_image_freshness
  action_download_fw
  action_extract_fw
  action_bootstrap_debian
  action_validate
  action_package
  log "🎉 Full pipeline completed successfully."
}

# --- MENUS -------------------------------------------------------------------
simple_menu() {
  clear
  cat <<EOF
========================================================
 K2Rebuild Simple Menu
========================================================
1) Run full firmware rebuild pipeline (auto-download, extract, rebuild, test, package)
2) Exit
========================================================
EOF
  read -rp "Select option [1-2]: " choice
  case "$choice" in
    1) action_full_pipeline ;;
    2) echo "Bye!"; exit 0 ;;
    *) echo "Invalid option."; sleep 1; simple_menu ;;
  esac
}

advanced_menu() {
  clear
  cat <<EOF
========================================================
 K2Rebuild Advanced Menu
========================================================
1) Ensure freshest container image
2) Download latest firmware
3) Extract firmware image
4) Bootstrap Debian rootfs
5) Validate (original vs rebuilt)
6) Package rebuilt rootfs
7) Full pipeline (all steps)
8) Exit
========================================================
EOF
  read -rp "Select option [1-8]: " choice
  case "$choice" in
    1) ensure_image_freshness ;;
    2) action_download_fw ;;
    3) action_extract_fw ;;
    4) action_bootstrap_debian ;;
    5) action_validate ;;
    6) action_package ;;
    7) action_full_pipeline ;;
    8) echo "Bye!"; exit 0 ;;
    *) echo "Invalid option."; sleep 1 ;;
  esac
}

# --- MAIN --------------------------------------------------------------------
main() {
  ensure_output_dir
  ensure_image_freshness
  local mode="${1:-menu}"
  if [[ "$mode" == "--auto" ]]; then
    # automatic noninteractive mode (full pipeline)
    action_full_pipeline
    exit 0
  fi

  echo "Choose menu mode:"
  echo "1) Simple (full automation)"
  echo "2) Advanced (manual steps)"
  read -rp "> " menumode
  case "$menumode" in
    1|"") simple_menu ;;
    2) advanced_menu ;;
    *) simple_menu ;;
  esac
}

main "$@"
