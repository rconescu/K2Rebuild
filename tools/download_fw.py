#!/opt/k2env/bin/python3
import os, re, sys, requests
from bs4 import BeautifulSoup
from tools.logger import log
from tools.checkpoint import stage_done

PAGE = "https://www.creality.com/download/creality-k2-plus-cfs-combo"
OUT_DIR = "/repo/output"
OUT_IMG = os.path.join(OUT_DIR, "latest_firmware.img")
HDRS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13.5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Referer": "https://www.creality.com/",
}

def find_url():
    log(f"🔍 Fetching {PAGE}")
    r = requests.get(PAGE, headers=HDRS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    links = [a["href"] for a in soup.find_all("a", href=True) if a["href"].endswith(".img")]
    if links:
        return links[0]
    m = re.search(r"https?://[^\s\"']+\.img", r.text)
    return m.group(0) if m else None

def download(url: str, out: str):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    log(f"⬇️  Downloading → {url}")
    with requests.get(url, headers=HDRS, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(out, "wb") as f:
            for chunk in r.iter_content(8192):
                if chunk: f.write(chunk)
    log(f"✅ Saved → {out}")

def main():
    if os.path.exists(OUT_IMG):
        log(f"⏩ Found existing firmware: {OUT_IMG}")
        stage_done("downloaded", firmware=OUT_IMG)
        return
    url = find_url()
    if not url:
        log("❌ Could not find firmware URL")
        sys.exit(1)
    download(url, OUT_IMG)
    stage_done("downloaded", firmware=OUT_IMG)

if __name__ == "__main__":
    main()
