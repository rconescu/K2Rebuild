#!/usr/bin/env bash
set -euo pipefail

# ===============================================================
#  K2Rebuild Firmware Build & Management Orchestrator (Final)
# ===============================================================

# --- Configuration ---
HOST_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST_OUTPUT_DIR="${HOST_REPO_ROOT}/output"
HOST_TOOLS_DIR="${HOST_REPO_ROOT}/tools"

CONTAINER_OUTPUT_DIR="/repo/output"
CONTAINER_TOOLS_DIR="/tools"
CHECKPOINT_JSON="${HOST_OUTPUT_DIR}/progress.json"
SSH_CONFIG_JSON="${HOST_OUTPUT_DIR}/ssh_config.json"
AUTOHEAL_RETRIES="${AUTOHEAL_RETRIES:-2}"

# --- Validate repo structure ---
if [[ ! -d "$HOST_OUTPUT_DIR" ]]; then
  echo "❌ ERROR: Expected output directory not found: $HOST_OUTPUT_DIR"
  echo "   → Please ensure you're running this script from the K2Rebuild repository root."
  exit 1
fi

if [[ ! -d "$HOST_TOOLS_DIR" ]]; then
  echo "❌ ERROR: Expected tools directory not found: $HOST_TOOLS_DIR"
  echo "   → Verify your ./tools folder exists and contains the orchestrator scripts."
  exit 1
fi

# --- Utility functions ---
timestamp() { date +"%Y-%m-%d %H:%M:%S"; }

docker_exec() {
  docker compose run --rm k2rebuild bash -lc "$1"
}

pause() { read -rp "Press Enter to continue..."; }

print_checkpoint() {
  if [[ -f "$CHECKPOINT_JSON" ]]; then
    echo
    echo "Checkpoint:"
    jq -r '"\(.stage) (\(.timestamp))\n→ \(.description)"' "$CHECKPOINT_JSON"
  else
    echo
    echo "(no progress.json yet)"
  fi
  echo
}

# --- SSH verification helper ---
verify_ssh() {
  local host user password port
  host="$1"; user="$2"; password="$3"; port="$4"

  echo "[$(timestamp)] 🔌 Testing SSH connection to ${user}@${host}:${port}..."
  if docker_exec "sshpass -p '$password' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 ${user}@${host} -p ${port} 'echo connected'" >/dev/null 2>&1; then
    echo "[$(timestamp)] ✅ SSH connection verified."
    return 0
  else
    echo "[$(timestamp)] ❌ SSH connection failed."
    return 1
  fi
}

# --- Menu actions ---
enter_credentials() {
  echo "Enter your printer credentials:"
  read -rp "IP Address: " host
  read -rp "Username [root]: " user
  user="${user:-root}"
  read -rsp "Password: " password
  echo
  read -rp "Port [22]: " port
  port="${port:-22}"

  echo "[$(timestamp)] 🔍 Verifying SSH connection..."
  if verify_ssh "$host" "$user" "$password" "$port"; then
    jq -n --arg host "$host" --arg user "$user" --arg password "$password" --arg port "$port" \
      '{host:$host, user:$user, password:$password, port:$port}' > "$SSH_CONFIG_JSON"
    echo "[$(timestamp)] 💾 Credentials verified and saved."
  else
    echo "[$(timestamp)] 🚫 Credentials not saved (SSH verification failed)."
  fi
  pause
}

fetch_device_state() {
  if [[ ! -f "$SSH_CONFIG_JSON" ]]; then
    echo "❌ SSH credentials not found. Please enter them first."
    pause
    return
  fi

  local host user password port
  host=$(jq -r .host "$SSH_CONFIG_JSON")
  user=$(jq -r .user "$SSH_CONFIG_JSON")
  password=$(jq -r .password "$SSH_CONFIG_JSON")
  port=$(jq -r .port "$SSH_CONFIG_JSON")

  echo "[$(timestamp)] 📡 Launching fetch_device_state.py (SSH metadata fetch)..."
  docker_exec "python3 ${CONTAINER_TOOLS_DIR}/fetch_device_state.py \
    --host ${host} --user ${user} --password ${password} --port ${port}" || true

  echo
  echo "🔎 Immediately checking for latest firmware from Creality and comparing versions…"
  docker_exec "python3 ${CONTAINER_TOOLS_DIR}/generate_fw.py"
  pause
}

build_firmware() {
  if [[ ! -f "$CHECKPOINT_JSON" ]]; then
    echo "❌ Build blocked: device files or extracted image not found."
    echo "→ Run 'Fetch device state' first."
    pause
    return
  fi

  echo "▶️ Launching firmware build pipeline..."
  docker_exec "python3 ${CONTAINER_TOOLS_DIR}/orchestrator.py build" || true
  pause
}

set_autoheal() {
  read -rp "Enter new auto-heal retry count (current: ${AUTOHEAL_RETRIES}): " retries
  export AUTOHEAL_RETRIES="${retries:-2}"
  echo "✅ Auto-heal retries set to ${AUTOHEAL_RETRIES}"
  pause
}

clean_output() {
  echo "⚠️  This will remove all generated output files. Continue? [y/N]"
  read -r confirm
  if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
    rm -rf "${HOST_OUTPUT_DIR:?}/"*
    echo "✅ Output directory cleaned."
  fi
  pause
}

show_progress() {
  if [[ -f "$CHECKPOINT_JSON" ]]; then
    echo "📊 Progress details:"
    jq . "$CHECKPOINT_JSON"
  else
    echo "No progress file found."
  fi
  pause
}

# --- Menu loop ---
while true; do
  clear
  echo "==========================================================================================================================="
  echo " K2Rebuild Automatic Firmware Runner"
  echo "==========================================================================================================================="
  echo "Time: $(timestamp)  |  Output: ${HOST_OUTPUT_DIR}"

  print_checkpoint

  cat <<EOF
1) Enter / verify printer SSH & save
2) Fetch device state (from printer) + check latest firmware
3) Build / Resume pipeline (auto-heal)
4) Set auto-heal retry count (current: ${AUTOHEAL_RETRIES})
5) Clean output folder
6) Show progress details
7) Exit
EOF

  echo
  read -rp "Select: " choice
  case "$choice" in
    1) enter_credentials ;;
    2) fetch_device_state ;;
    3) build_firmware ;;
    4) set_autoheal ;;
    5) clean_output ;;
    6) show_progress ;;
    7) echo "👋 Exiting..."; exit 0 ;;
    *) echo "Invalid option."; pause ;;
  esac
done
