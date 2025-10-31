#!/usr/bin/env bash
# ============================================================
#  run_fwtool.sh - Full Remote Firmware Build/Fetch Runner
# ============================================================

set -e
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="${BASE_DIR}/output"
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

echo "========================================="
echo " K2Rebuild Automatic Firmware Runner"
echo "========================================="
echo "${TIMESTAMP} | Invoked: $@"
echo

MODE="build"
HOST=""
USER="root"
PASS=""
KEY=""
PORT="22"

# ------------------------------------------------------------
# Parse arguments
# ------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --fetch) MODE="fetch"; shift ;;
    --build) MODE="build"; shift ;;
    --host) HOST="$2"; shift 2 ;;
    --user) USER="$2"; shift 2 ;;
    --password) PASS="$2"; shift 2 ;;
    --key) KEY="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

echo "${TIMESTAMP} | ▶️ Mode: $MODE"
[ "$MODE" = "fetch" ] && echo "→ Fetch from host: ${HOST}"

# ------------------------------------------------------------
# Container execution
# ------------------------------------------------------------
if [ "$MODE" = "fetch" ]; then
  docker compose run --rm \
    -e FETCH_DEVICE=1 \
    -e DEVICE_HOST="$HOST" \
    -e DEVICE_USER="$USER" \
    -e DEVICE_PASS="$PASS" \
    -e DEVICE_KEY="$KEY" \
    -e DEVICE_PORT="$PORT" \
    k2rebuild python3 /tools/orchestrator.py fetch
else
  # 🧩 Note: For build, don’t pass 'build' arg — orchestrator defaults to build mode
  docker compose run --rm \
    k2rebuild python3 /tools/orchestrator.py
fi
