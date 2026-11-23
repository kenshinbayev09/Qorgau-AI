"""End-to-end API scenarios through FastAPI's TestClient (network checks disabled)."""

import io

import pytest
from conftest import MODEL_DIR
from fastapi.testclient import TestClient

from app.config import Settings
from app.deepfake.service import MediaService
from app.main import create_app


@pytest.fixture()
def client(tmp_path):
    cfg = Settings()
    cfg.network_checks_enabled = False
    cfg.rate_limit_per_minute = 0
    media = MediaService(tmp_path / "no-weights", isolation="inline", tmp_dir=tmp_path)
    with TestClient(create_app(cfg, media_service=media)) as c:
        yield c


def test_health_reports_components(client):
    h = client.get("/api/v1/health").json()
    assert h["status"] == "ok"
    assert h["deepfake_model"]["status"] == "not_connected"
    assert h["external_services"] == {"safe_browsing": False, "llm_explanations": False, "virustotal": False}


def test_url_check_full_flow(client):
    r = client.post("/api/v1/url/check", json={"url": "http://kaspi.kz.secure-login.xyz/verify?token=abc123"})
    assert r.status_code == 200
    d = r.json()
    assert d["kind"] == "url" and d["category"] == "high"
    assert "abc123" not in d["input"]  # secret-looking params are masked in the echo
    assert {c["id"] for c in d["checks"]} >= {"url_structure", "ml_model", "redirects", "reputation"}
    assert d["advice"] and d["analyzed_at"]


@pytest.mark.parametrize("url,code", [("javascript:alert(1)", "invalid_url:unsupported_scheme"),
                                      ("not a url", "invalid_url:invalid_url"),
                                      ("http://localhost:3000", "invalid_url:invalid_host")])
def test_url_check_invalid(client, url, code):
    r = client.post("/api/v1/url/check", json={"url": url})
    assert r.status_code == 422 and r.json()["error"]["code"] == code


def test_bad_body(client):
    assert client.post("/api/v1/url/check", json={}).json()["error"]["code"] == "invalid_request"


def test_media_without_model_is_honest_503(client):
    r = client.post("/api/v1/media/upload", files={"file": ("a.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 64), "image/png")})
    assert r.status_code == 503 and r.json()["error"]["code"] == "model_unavailable"


def test_demo_is_labelled(client):
    d = client.get("/api/v1/demo/media").json()
    assert d["demo"] is True and d["model"]["status"] == "demo"


def test_agent_endpoint(client):
    d = client.post("/api/v1/agent/run", json={"text": "проверь paypa1.com", "lang": "kk"}).json()
    assert d["state"] == "done" and d["tool_used"] == "url_check" and d["result"]["kind"] == "url"
    assert d["trace"][0]["state"] == "observe"


def test_rate_limit(tmp_path):
    cfg = Settings()
    cfg.network_checks_enabled = False
    cfg.rate_limit_per_minute = 2
    media = MediaService(tmp_path / "x", isolation="inline", tmp_dir=tmp_path)
    with TestClient(create_app(cfg, media_service=media)) as c:
        codes = [c.post("/api/v1/url/check", json={"url": "example.org"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
