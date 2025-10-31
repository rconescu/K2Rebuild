#!/opt/k2env/bin/python3
import os, shutil, subprocess

def is_nonempty_dir(path: str) -> bool:
    return os.path.isdir(path) and any(os.scandir(path))

def run_ok(cmd: list, cwd=None) -> bool:
    return subprocess.call(cmd, cwd=cwd) == 0

def sh(cmd: list, cwd=None):
    subprocess.check_call(cmd, cwd=cwd)

def bytes_of(path: str) -> int:
    try:
        return os.path.getsize(path)
    except Exception:
        return 0

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def copy(src: str, dst: str):
    ensure_dir(os.path.dirname(dst))
    shutil.copy2(src, dst)
