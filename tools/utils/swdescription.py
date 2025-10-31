#!/opt/k2env/bin/python3
import re

def update_rootfs_hash_size(text: str, sha256: str, size: int) -> str:
    text = re.sub(r'(sha256\s*=\s*)".*?"', rf'\1"{sha256}"', text)
    text = re.sub(r'(size\s*=\s*)\d+;', rf'\1{size};', text)
    return text
