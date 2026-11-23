import io
import shutil

import cv2
import numpy as np
import pytest
from conftest import FIXTURES, MODEL_DIR, requires_deepfake_weights
from PIL import Image

from app.deepfake.analysis import Limits
from app.deepfake.media import MediaError, sniff
from app.deepfake.service import MediaService


def png_bytes(color=(120, 200, 90), size=(300, 300)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def make_video(path, seconds=2.0, fps=10, size=(160, 120)):
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    for i in range(int(seconds * fps)):
        frame = np.full((size[1], size[0], 3), (i * 7) % 255, np.uint8)
        w.write(frame)
    w.release()
    return path


# ---------- format sniffing (actual bytes, not file name / declared type) ----------
def test_sniff_formats():
    assert sniff(png_bytes()[:64]).fmt == "png"
    assert sniff(b"\xff\xd8\xff\xe0" + b"\0" * 20).fmt == "jpeg"
    assert sniff(b"\0\0\0\x18ftypmp42" + b"\0" * 8).kind == "video"
    assert sniff(b"\0\0\0\x14ftypqt  " + b"\0" * 8).fmt == "mov"


@pytest.mark.parametrize("head,code", [
    (b"hello world, this is text", "unsupported_format"),
    (b"<!DOCTYPE html><html><body>", "not_media_html"),
    (b"\0\0\0\x18ftypheic" + b"\0" * 8, "unsupported_format"),
    (b"%PDF-1.7\n" + b"\0" * 10, "unsupported_format"),
])
def test_sniff_rejects(head, code):
    with pytest.raises(MediaError) as e:
        sniff(head)
    assert e.value.code == code


def svc(tmp_path, model_dir=MODEL_DIR, **kw):
    return MediaService(model_dir, isolation=kw.pop("isolation", "inline"), tmp_dir=tmp_path, **kw)


# ---------- model availability ----------
def test_model_not_connected(tmp_path):
    s = svc(tmp_path, tmp_path / "no-weights")
    assert s.model_info()["status"] == "not_connected"
    with pytest.raises(MediaError) as e:
        s.analyse_upload(io.BytesIO(png_bytes()))
    assert e.value.code == "model_unavailable" and e.value.http_status == 503


def test_model_load_error_is_reported(tmp_path):
    broken = tmp_path / "broken"
    broken.mkdir()
    for f in ("config.json", "preprocessor_config.json"):
        shutil.copy(MODEL_DIR / f, broken / f) if (MODEL_DIR / f).exists() else (broken / f).write_text("{}")
    (broken / "model.safetensors").write_bytes(b"corrupted weights")
    s = svc(tmp_path, broken)
    with open(FIXTURES / "lincoln_pd.jpg", "rb") as f:
        with pytest.raises(MediaError) as e:
            s.analyse_upload(f)
    assert e.value.code == "model_unavailable"
    assert s.model_info()["status"] == "error"


# ---------- limits / unsupported input ----------
def test_upload_size_limit_and_temp_cleanup(tmp_path):
    s = svc(tmp_path, max_upload_mb=1)
    with pytest.raises(MediaError) as e:
        s.analyse_upload(io.BytesIO(b"\xff\xd8\xff" + b"0" * (2 * 1024 * 1024)))
    assert e.value.code == "too_large"
    assert list((tmp_path / "qorgau_media").iterdir()) == []


@requires_deepfake_weights
def test_unsupported_file_rejected_and_cleaned(tmp_path):
    s = svc(tmp_path)
    with pytest.raises(MediaError) as e:
        s.analyse_upload(io.BytesIO(b"just some text pretending to be a video"))
    assert e.value.code == "unsupported_format"
    assert list((tmp_path / "qorgau_media").iterdir()) == []


@requires_deepfake_weights
def test_social_page_link_needs_upload(tmp_path):
    with pytest.raises(MediaError) as e:
        svc(tmp_path).analyse_url("https://www.instagram.com/reel/abc123/")
    assert e.value.code == "social_page"


@requires_deepfake_weights
def test_image_without_face_is_insufficient(tmp_path):
    r = svc(tmp_path).analyse_upload(io.BytesIO(png_bytes()))
    assert r["status"] == "insufficient" and r["reason"] == "no_face" and r["score"] is None
    assert r["frames"][0]["has_face"] is False


@requires_deepfake_weights
def test_video_without_faces_is_insufficient(tmp_path):
    path = make_video(tmp_path / "v.mp4", seconds=3)
    with open(path, "rb") as f:
        r = svc(tmp_path).analyse_upload(f)
    assert r["media_type"] == "video" and r["status"] == "insufficient"
    assert 1 <= r["aggregate"]["frames_sampled"] <= 16 and r["aggregate"]["frames_with_face"] == 0


@requires_deepfake_weights
def test_video_duration_limit(tmp_path):
    path = make_video(tmp_path / "long.mp4", seconds=3)
    with open(path, "rb") as f, pytest.raises(MediaError) as e:
        svc(tmp_path, limits=Limits(max_video_seconds=1)).analyse_upload(f)
    assert e.value.code == "video_too_long"


@requires_deepfake_weights
def test_face_image_runs_real_model(tmp_path):
    with open(FIXTURES / "lincoln_pd.jpg", "rb") as f:
        r = svc(tmp_path).analyse_upload(f)
    assert r["status"] == "done" and r["frames"][0]["has_face"]
    assert 0.0 <= r["score"] <= 1.0 and r["category"] in ("low", "suspicious", "high")
    assert [s["id"] for s in r["stages"]][-2:] == ["inference", "aggregate"]
    assert r["model"]["name"].startswith("buildborderless/") and r["demo"] is False


@requires_deepfake_weights
def test_process_isolation_worker(tmp_path):
    s = svc(tmp_path, isolation="process", timeout_s=120)
    try:
        r = s.analyse_upload(io.BytesIO(png_bytes()))
        assert r["reason"] == "no_face"
    finally:
        s.shutdown()
