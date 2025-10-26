#!/usr/bin/env python3
"""
download_latest_k2plus_fw.py
Self-contained Creality K2 Plus firmware downloader.
Auto-installs dependencies, scrapes firmware URL, downloads latest .img.
"""

import os, re, sys, subprocess

# ---------------------------------------------------------------------
# Ensure dependencies
# ---------------------------------------------------------------------
for pkg in ("requests", "beautifulsoup4"):
    try:
        __import__(pkg)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

import requests
from bs4 import BeautifulSoup

PAGE_URL = "https://www.creality.com/download/creality-k2-plus-cfs-combo"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_1) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Referer": PAGE_URL,
}

print(f"🔍 Fetching firmware list from {PAGE_URL}")
try:
    resp = requests.get(PAGE_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
except Exception as e:
    print(f"❌ Failed to fetch page: {e}")
    sys.exit(1)

soup = BeautifulSoup(resp.text, "html.parser")
links = [a["href"] for a in soup.find_all("a", href=True)]
img_links = [l for l in links if l.endswith(".img") or "firmware" in l]

if not img_links:
    img_links = re.findall(r"https://[^\s\"']+\.img", resp.text)

if not img_links:
    print("❌ No firmware .img link found on the page.")
    sys.exit(1)

fw_url = sorted(set(img_links))[-1]
fname = os.path.basename(fw_url)

print(f"✅ Found firmware URL:\n{fw_url}")
print(f"⬇️  Downloading → {fname}")

try:
    with requests.get(fw_url, headers=HEADERS, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(fname, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    print(f"✅ Download complete: {fname}")
except Exception as e:
    print(f"❌ Download failed: {e}")
    sys.exit(2)

print(f"📦 Saved as {fname} ({os.path.getsize(fname)/(1024*1024):.2f} MB)")
print("Done.")
