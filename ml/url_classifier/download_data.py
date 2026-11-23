"""Download the two public phishing URL datasets used for training.

1. PhiUSIIL Phishing URL Dataset (UCI ML Repository, id 967), CC BY 4.0.
   Prasad, A. & Chandra, S. (2024). Computers & Security, 136, 103545.
2. Web page phishing detection dataset, Hannousse & Yahiouche (2021), CC BY 4.0,
   mirrored on Hugging Face as `pirocheto/phishing-url` (pinned revision below).
"""

from __future__ import annotations

import hashlib
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "ml" / "data" / "raw"

PHIUSIIL_URL = "https://archive.ics.uci.edu/static/public/967/phiusiil+phishing+url+dataset.zip"
PHIUSIIL_SHA256 = "0a639fd03aea6308c5b1c10c92aa23c2ce1505447a9137271865cd0badc9a59a"  # zip as downloaded 2026-11-08
HF_REV = "1375d450d4540205ac11781b807249c9509739cd"
HF_BASE = f"https://huggingface.co/datasets/pirocheto/phishing-url/resolve/{HF_REV}/data"


def fetch(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url} -> {dest}")
    with urllib.request.urlopen(url, timeout=120) as r, open(dest, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)


def main() -> None:
    z = RAW / "phiusiil.zip"
    if not (RAW / "PhiUSIIL_Phishing_URL_Dataset.csv").exists():
        fetch(PHIUSIIL_URL, z)
        digest = hashlib.sha256(z.read_bytes()).hexdigest()
        if digest != PHIUSIIL_SHA256:
            print(f"WARNING: sha256 {digest} differs from the version used for the reported metrics")
        with zipfile.ZipFile(z) as zf:
            zf.extractall(RAW)
    for part in ("train", "test"):
        dest = RAW / "hannousse" / f"{part}.parquet"
        if not dest.exists():
            fetch(f"{HF_BASE}/{part}.parquet", dest)
    print("Done.")


if __name__ == "__main__":
    main()
