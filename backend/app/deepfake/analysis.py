"""Media analysis pipeline (runs inside the isolated worker process).

image: decode -> face detection -> face crop -> ViT inference
video: probe (duration/fps) -> sample <= N frames uniformly -> per frame:
       face detection -> crop -> batched ViT inference -> aggregation

Aggregation: median of per-frame P(deepfake) over frames that contain a face.
Median is used so that a single outlier frame cannot decide the verdict.
"""

from __future__ import annotations

import base64
import io
import statistics
import time
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageOps

from .detector import DeepfakeDetector
from .faces import crop_face, detect_faces
from .media import MediaError

# Пороги подобраны по распределению оценок на выборке DeepFakeFace (см. docs/technical_report.md):
# настоящие фото почти всегда ниже 0.05; подделки — в основном выше 0.5.
LOW_MAX, SUSPICIOUS_MAX = 0.05, 0.50
MIN_FACE_FRAMES_VIDEO = 3

LIMITATIONS = [
    "pretrained_model_unknown_data",  # training data of the third-party model is not fully documented
    "frame_level_only",  # each frame is scored independently: no temporal/audio/lip-sync analysis
    "face_crops_only",  # only the largest detected frontal face per frame is analysed
    "compression_sensitive",  # re-encoding / filters / low resolution change scores
    "not_proof",  # a score is a model estimate, not evidence
]


@dataclass
class Limits:
    max_video_seconds: int = 60
    max_video_frames: int = 16
    max_image_pixels: int = 40_000_000


class _Stages:
    def __init__(self):
        self.items: list[dict[str, Any]] = []
        self._t = time.monotonic()
        self._current: str | None = None

    def start(self, sid: str) -> None:
        self._close()
        self._current, self._t = sid, time.monotonic()

    def _close(self, status: str = "done") -> None:
        if self._current:
            self.items.append({"id": self._current, "status": status, "ms": int((time.monotonic() - self._t) * 1000)})
            self._current = None

    def finish(self, status: str = "done") -> list[dict[str, Any]]:
        self._close(status)
        return self.items


def _thumb(img: Image.Image, side: int = 112) -> str:
    im = img.convert("RGB").copy()
    im.thumbnail((side, side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=70)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def category_for(score: float) -> str:
    return "low" if score < LOW_MAX else "suspicious" if score < SUSPICIOUS_MAX else "high"


def _load_image(path: str, limits: Limits) -> Image.Image:
    Image.MAX_IMAGE_PIXELS = limits.max_image_pixels
    try:
        with Image.open(path) as im:
            if im.width * im.height > limits.max_image_pixels:
                raise MediaError("image_too_large", "Image resolution too high", 413)
            im = ImageOps.exif_transpose(im)
            return im.convert("RGB")
    except Image.DecompressionBombError as exc:
        raise MediaError("image_too_large", "Image resolution too high", 413) from exc
    except (OSError, SyntaxError, ValueError) as exc:
        raise MediaError("unreadable", "Image could not be decoded") from exc


def _sample_video(path: str, limits: Limits, stages: _Stages) -> tuple[list[tuple[float, Image.Image]], dict]:
    import cv2

    cap = cv2.VideoCapture(path)
    try:
        if not cap.isOpened():
            raise MediaError("unreadable", "Video could not be opened")
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if fps <= 0 or count <= 0:
            raise MediaError("unreadable", "Video duration could not be determined")
        duration = count / fps
        if duration > limits.max_video_seconds:
            raise MediaError("video_too_long", f"Video longer than {limits.max_video_seconds}s")
        if width * height > limits.max_image_pixels:
            raise MediaError("image_too_large", "Video resolution too high", 413)
        n = max(1, min(limits.max_video_frames, int(duration * 2) or 1, count))
        stages.start("extract_frames")
        frames: list[tuple[float, Image.Image]] = []
        for k in range(n):
            idx = int((k + 0.5) * count / n)
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            frames.append((idx / fps, Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))))
        if not frames:
            raise MediaError("unreadable", "No frames could be decoded")
        return frames, {"duration_s": round(duration, 2), "fps": round(fps, 2), "width": width, "height": height,
                        "frames_total": count}
    finally:
        cap.release()


def analyse(path: str, kind: str, detector: DeepfakeDetector, limits: Limits) -> dict[str, Any]:
    stages = _Stages()
    meta: dict[str, Any] = {}
    stages.start("decode")
    if kind == "image":
        img = _load_image(path, limits)
        frames = [(0.0, img)]
        meta = {"width": img.width, "height": img.height}
    else:
        frames, meta = _sample_video(path, limits, stages)

    stages.start("detect_faces")
    crops: list[Image.Image | None] = []
    for _, im in frames:
        boxes = detect_faces(im)
        crops.append(crop_face(im, boxes[0]) if boxes else None)

    face_idx = [i for i, c in enumerate(crops) if c is not None]
    scores: dict[int, float] = {}
    if face_idx:
        stages.start("inference")
        detector.load()
        if detector.model is None:
            raise MediaError("model_unavailable", detector.error or "model not loaded", 503)
        preds = detector.predict([crops[i] for i in face_idx])
        scores = dict(zip(face_idx, preds))

    stages.start("aggregate")
    frame_items = []
    for i, (t, im) in enumerate(frames):
        frame_items.append({
            "index": i,
            "t_sec": round(t, 2),
            "has_face": crops[i] is not None,
            "score": None if i not in scores else round(scores[i], 4),
            "thumb": _thumb(crops[i] if crops[i] is not None else im),
        })
    vals = list(scores.values())
    min_needed = 1 if kind == "image" else min(MIN_FACE_FRAMES_VIDEO, len(frames))
    result: dict[str, Any] = {
        "media_type": kind,
        "meta": meta,
        "frames": frame_items,
        "top_frames": [i for i, _ in sorted(scores.items(), key=lambda kv: -kv[1])[:3]],
        "limitations": LIMITATIONS,
    }
    if not vals:
        result.update(status="insufficient", category="insufficient", score=None, reason="no_face")
    elif len(vals) < min_needed:
        result.update(status="insufficient", category="insufficient", score=None, reason="too_few_face_frames")
    else:
        med = statistics.median(vals)
        result.update(status="done", category=category_for(med), score=round(med, 4), reason=None)
    result["aggregate"] = {
        "method": "median",
        "frames_sampled": len(frames),
        "frames_with_face": len(vals),
        "median": round(statistics.median(vals), 4) if vals else None,
        "mean": round(statistics.fmean(vals), 4) if vals else None,
        "max": round(max(vals), 4) if vals else None,
        "share_over_0_5": round(sum(v >= 0.5 for v in vals) / len(vals), 3) if vals else None,
    }
    result["stages"] = stages.finish()
    return result
