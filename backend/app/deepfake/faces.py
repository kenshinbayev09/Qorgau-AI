"""Face localisation with OpenCV's bundled Haar cascade (classical CV, no download).

The deepfake classifier was fine-tuned on face images, so frames without a
detectable frontal face are excluded instead of being scored.
"""

from __future__ import annotations

import threading

import cv2
import numpy as np
from PIL import Image

_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
_local = threading.local()


def _cascade() -> cv2.CascadeClassifier:
    c = getattr(_local, "cascade", None)
    if c is None:
        c = cv2.CascadeClassifier(_CASCADE_PATH)
        if c.empty():
            raise RuntimeError("Haar cascade file could not be loaded")
        _local.cascade = c
    return c


def detect_faces(img: Image.Image, max_side: int = 640) -> list[tuple[int, int, int, int]]:
    """Return face boxes (x, y, w, h) in original image coordinates, largest first."""
    rgb = np.asarray(img.convert("RGB"))
    h, w = rgb.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    small = cv2.resize(rgb, (int(w * scale), int(h * scale))) if scale < 1 else rgb
    gray = cv2.equalizeHist(cv2.cvtColor(small, cv2.COLOR_RGB2GRAY))
    min_side = max(24, int(min(small.shape[:2]) * 0.08))
    boxes = _cascade().detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(min_side, min_side))
    out = [(int(x / scale), int(y / scale), int(bw / scale), int(bh / scale)) for (x, y, bw, bh) in boxes]
    return sorted(out, key=lambda b: -b[2] * b[3])


def crop_face(img: Image.Image, box: tuple[int, int, int, int], margin: float = 0.25) -> Image.Image:
    x, y, w, h = box
    side = int(max(w, h) * (1 + 2 * margin))
    cx, cy = x + w / 2, y + h / 2
    left = int(max(0, cx - side / 2))
    top = int(max(0, cy - side / 2))
    right = int(min(img.width, cx + side / 2))
    bottom = int(min(img.height, cy + side / 2))
    return img.crop((left, top, right, bottom))
