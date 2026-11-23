"""Fetch a small, reproducible labelled sample of the DeepFakeFace (DFF) dataset.

Dataset: OpenRL/DeepFakeFace on Hugging Face (license: OpenRAIL, research use).
  * real images:  wiki.zip     (faces from IMDB-WIKI)
  * fake images:  insight.zip  (InsightFace face swaps), inpainting.zip, text2img.zip
Only the selected files are downloaded, using HTTP Range requests into the
remote zip archives (the full archives are ~1-1.8 GB each).

Usage:
  python ml/deepfake/fetch_dff_sample.py --per-class 200 --fake-sets insight inpainting
Output: ml/data/deepfake_eval/{real,fake}/*.jpg  + manifest.json
"""

from __future__ import annotations

import argparse
import io
import json
import random
import zipfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
REV = "eb2a54fbf2567790bd3dc61d09fdaade6bb6c31c"
BASE = f"https://huggingface.co/datasets/OpenRL/DeepFakeFace/resolve/{REV}"
OUT = ROOT / "ml" / "data" / "deepfake_eval"
IMG_EXT = (".jpg", ".jpeg", ".png")


class HttpRangeFile(io.RawIOBase):
    """Seekable read-only file over HTTP Range requests (enough for zipfile)."""

    def __init__(self, url: str, client: httpx.Client):
        self.client = client
        r = client.head(url, follow_redirects=True)
        r.raise_for_status()
        self.url = str(r.url)
        self.size = int(r.headers["content-length"])
        self.pos = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=io.SEEK_SET):
        self.pos = {io.SEEK_SET: offset, io.SEEK_CUR: self.pos + offset, io.SEEK_END: self.size + offset}[whence]
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        if n == 0 or self.pos >= self.size:
            return b""
        end = min(self.size, self.pos + n) - 1
        r = self.client.get(self.url, headers={"Range": f"bytes={self.pos}-{end}"})
        r.raise_for_status()
        data = r.content
        self.pos += len(data)
        return data

    def readinto(self, b):
        data = self.read(len(b))
        b[: len(data)] = data
        return len(data)


def sample_from(archive: str, k: int, dest: Path, rng: random.Random, client: httpx.Client) -> list[str]:
    f = HttpRangeFile(f"{BASE}/{archive}", client)
    with zipfile.ZipFile(io.BufferedReader(f, buffer_size=1 << 20)) as zf:
        names = sorted(n for n in zf.namelist() if n.lower().endswith(IMG_EXT))
        chosen = rng.sample(names, min(k, len(names)))
        dest.mkdir(parents=True, exist_ok=True)
        for i, name in enumerate(chosen):
            data = zf.read(name)
            safe = archive.split(".")[0] + "__" + name.replace("/", "_")
            (dest / safe).write_bytes(data)
            if (i + 1) % 50 == 0:
                print(f"  {archive}: {i + 1}/{len(chosen)}", flush=True)
    return chosen


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class", type=int, default=200)
    ap.add_argument("--fake-sets", nargs="+", default=["insight", "inpainting"],
                    choices=["insight", "inpainting", "text2img"])
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    manifest = {"dataset": "OpenRL/DeepFakeFace", "revision": REV, "license": "openrail (research use)",
                "seed": args.seed, "real": {}, "fake": {}}
    with httpx.Client(timeout=60, headers={"User-Agent": "qorgau-ai-eval/0.1"}) as client:
        manifest["real"]["wiki.zip"] = sample_from("wiki.zip", args.per_class, OUT / "real", rng, client)
        per_fake = max(1, args.per_class // len(args.fake_sets))
        for s in args.fake_sets:
            manifest["fake"][f"{s}.zip"] = sample_from(f"{s}.zip", per_fake, OUT / "fake", rng, client)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print("Saved sample to", OUT)


if __name__ == "__main__":
    main()
