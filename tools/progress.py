#!/usr/bin/env python3
# progress.py — human-friendly progress tracking for K2Rebuild

import os, json, sys, time
from typing import Any, Dict, List
try:
    from colorama import init as colorama_init, Fore, Style
except Exception:
    class _Dummy:
        RESET_ALL = ""
    class _DummyFore(_Dummy):
        RED=GREEN=YELLOW=BLUE=CYAN=MAGENTA=WHITE=""
    class _DummyStyle(_Dummy): ...
    Fore=_DummyFore(); Style=_DummyStyle()
    def colorama_init(): pass

colorama_init()

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/repo/output")
PROG_JSON  = os.path.join(OUTPUT_DIR, "progress.json")

def _ensure_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def _read_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _write_json(path: str, data: Dict[str, Any]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp, path)

def _ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")

def pretty_stage(stage: str) -> str:
    mapping = {
        "none": "Not started",
        "detect_rootfs": "Detect firmware image",
        "unsquash": "Unpack rootfs",
        "inject_upstream": "Inject upstream components",
        "repack_fw": "Repack firmware",
        "validate_fw": "Validate firmware",
        "validate_failed": "Validate (failed)",
        "generate_fw": "Generate final artifacts",
        "finished": "Finished",
    }
    return mapping.get(stage, stage)

def update_progress(stage: str, message: str, status: str = "info", extra: Dict[str, Any] = None):
    _ensure_dir()
    data = _read_json(PROG_JSON)
    history: List[Dict[str, Any]] = data.get("history", [])
    entry = {
        "time": _ts(),
        "stage": stage,
        "status": status,
        "message": message,
    }
    if extra:
        entry["extra"] = extra
    history.append(entry)
    data["history"] = history
    data["current"] = stage
    _write_json(PROG_JSON, data)

    color = {"info": Fore.CYAN, "ok": Fore.GREEN, "warn": Fore.YELLOW, "error": Fore.RED}.get(status, "")
    print(f"{color}[progress]{Style.RESET_ALL} {pretty_stage(stage)} — {message}")

def get_history():
    """Return the entire progress history list (safe for UI/menus)."""
    data = _read_json(PROG_JSON)
    return data.get("history", [])

def current_stage() -> str:
    data = _read_json(PROG_JSON)
    return data.get("current", "none")

if __name__ == "__main__":
    # tiny CLI for debugging
    if len(sys.argv) >= 3 and sys.argv[1] == "log":
        update_progress(sys.argv[2], " ".join(sys.argv[3:]))
    else:
        print(json.dumps({"current": current_stage(), "history": get_history()}, indent=2))
