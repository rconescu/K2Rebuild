#!/usr/bin/env python3
# checkpoint.py — single source of truth for pipeline stage state

import os, json
from typing import Any, Dict

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/repo/output")
CHECKPOINT = os.path.join(OUTPUT_DIR, "checkpoint.json")

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

def get_checkpoint() -> Dict[str, Any]:
    _ensure_dir()
    data = _read_json(CHECKPOINT)
    if "stage" not in data:
        data["stage"] = "none"
    return data

def stage_done(stage: str, **kwargs):
    _ensure_dir()
    data = get_checkpoint()
    data["stage"] = stage
    if kwargs:
        data.setdefault("meta", {}).update(kwargs)
    _write_json(CHECKPOINT, data)

def last_successful_stage() -> str:
    try:
        data = get_checkpoint()
        return data.get("stage", "none")
    except Exception:
        return "none"

def require_files(files):
    """Raise FileNotFoundError if a required file is missing."""
    missing = [p for p in files if not os.path.exists(p)]
    if missing:
        raise FileNotFoundError("Missing required files: " + ", ".join(missing))
