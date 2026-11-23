"""Static DEMO result for the deepfake screen.

This is NOT an analysis of any user file. It is a fixed, hand-written example
used only in the app's explicitly labelled demo mode, so the UI can be shown
when the model weights are not installed. `demo: true` is always set and the
app shows a prominent "ДЕМО" badge.
"""

from __future__ import annotations

_SCORES = [0.12, 0.18, 0.15, None, 0.71, 0.66, 0.22, 0.19]


def demo_media_result() -> dict:
    frames = [{"index": i, "t_sec": i * 1.5, "has_face": s is not None, "score": s, "thumb": None}
              for i, s in enumerate(_SCORES)]
    vals = sorted(s for s in _SCORES if s is not None)
    return {
        "kind": "media",
        "demo": True,
        "source": "demo",
        "media_type": "video",
        "format": "mp4",
        "status": "done",
        "category": "low",
        "score": vals[len(vals) // 2 - 1] if len(vals) % 2 == 0 else vals[len(vals) // 2],
        "reason": None,
        "meta": {"duration_s": 12.0, "fps": 30.0, "width": 1280, "height": 720},
        "frames": frames,
        "top_frames": [4, 5, 6],
        "aggregate": {"method": "median", "frames_sampled": 8, "frames_with_face": 7, "median": 0.19,
                      "mean": round(sum(vals) / len(vals), 4), "max": 0.71, "share_over_0_5": round(2 / 7, 3)},
        "stages": [{"id": s, "status": "done", "ms": 0} for s in
                   ("validate_format", "decode", "extract_frames", "detect_faces", "inference", "aggregate")],
        "limitations": ["demo_data"],
        "model": {"name": "demo", "status": "demo", "version": None, "license": None},
    }
