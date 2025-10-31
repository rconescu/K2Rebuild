#!/usr/bin/env python3
import subprocess, os, hashlib, shutil

def run(cmd, cwd=None, check=True, capture=False, env=None):
    if capture:
        return subprocess.run(cmd, cwd=cwd, env=env, check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        subprocess.check_call(cmd, cwd=cwd, env=env)

def sha256sum(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def copy_file(src, dst):
    ensure_dir(os.path.dirname(dst))
    shutil.copy2(src, dst)

def write_text(path, text):
    ensure_dir(os.path.dirname(path))
    with open(path, "w") as f:
        f.write(text)
