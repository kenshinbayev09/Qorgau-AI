"""VirusTotal integration with a mocked HTTP transport: no network, no real key, no real upload."""

import hashlib
import io
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.deepfake.service import MediaService
from app.main import create_app
from app.security.virustotal import PUBLIC_UPLOAD_LIMIT, VirusTotalClient, verdict_for


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FakeVT:
    """Records calls and returns scripted responses."""

    def __init__(self, known: dict | None = None, analysis_status="completed", stats=None, fail_lookup=None):
        self.known = known  # stats for hashes that are "known"; None = 404
        self.analysis_status = analysis_status
        self.stats = stats or {"malicious": 0, "suspicious": 0, "undetected": 60, "harmless": 10}
        self.fail_lookup = fail_lookup
        self.calls: list[tuple[str, str]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, request.url.path))
        assert request.headers["x-apikey"] == "TEST_KEY"
        if request.method == "GET" and request.url.path.startswith("/api/v3/files/"):
            if self.fail_lookup:
                return httpx.Response(self.fail_lookup)
            if self.known is None:
                return httpx.Response(404, json={"error": {"code": "NotFoundError"}})
            return httpx.Response(200, json={"data": {"attributes": {"last_analysis_stats": self.known}}})
        if request.method == "POST" and request.url.path == "/api/v3/files":
            return httpx.Response(200, json={"data": {"type": "analysis", "id": "AN1"}})
        if request.method == "GET" and request.url.path == "/api/v3/analyses/AN1":
            return httpx.Response(200, json={"data": {"attributes": {"status": self.analysis_status, "stats": self.stats}}})
        return httpx.Response(500)


def client(fake: FakeVT, key: str | None = "TEST_KEY") -> VirusTotalClient:
    return VirusTotalClient(key, transport=httpx.MockTransport(fake), poll_interval=0, poll_timeout=0.5)


@pytest.fixture()
def sample(tmp_path):
    p = tmp_path / "sample.bin"
    p.write_bytes(b"harmless test content " * 10)
    return p


def test_verdicts():
    assert verdict_for({"malicious": 0, "suspicious": 0}) == "clean"
    assert verdict_for({"malicious": 1}) == "suspicious"
    assert verdict_for({"suspicious": 2}) == "suspicious"
    assert verdict_for({"malicious": 3}) == "malicious"


def test_disabled_without_key(sample):
    r = client(FakeVT(), key=None).scan(sample, allow_upload=True)
    assert r["status"] == "disabled" and r["sha256"] == sha(sample.read_bytes())


def test_known_hash_needs_no_upload(sample):
    fake = FakeVT(known={"malicious": 5, "suspicious": 0, "undetected": 60, "harmless": 0})
    r = client(fake).scan(sample, allow_upload=False)
    assert r["status"] == "done" and r["source"] == "known" and r["verdict"] == "malicious"
    assert all(m == "GET" for m, _ in fake.calls)  # only the hash went out


def test_unknown_hash_without_consent_is_not_uploaded(sample):
    fake = FakeVT(known=None)
    r = client(fake).scan(sample, allow_upload=False)
    assert r["status"] == "upload_required"
    assert ("POST", "/api/v3/files") not in fake.calls


def test_unknown_hash_with_consent_uploads_and_waits(sample):
    fake = FakeVT(known=None, analysis_status="completed")
    r = client(fake).scan(sample, allow_upload=True)
    assert r["status"] == "done" and r["source"] == "uploaded" and r["verdict"] == "clean"
    assert ("POST", "/api/v3/files") in fake.calls


def test_analysis_that_never_completes_times_out(sample):
    fake = FakeVT(known=None, analysis_status="queued")
    assert client(fake).scan(sample, allow_upload=True)["status"] == "timeout"


def test_rate_limit_is_reported(sample):
    assert client(FakeVT(fail_lookup=429)).scan(sample, allow_upload=True)["status"] == "rate_limited"


def test_server_error_is_failed_not_clean(sample):
    r = client(FakeVT(fail_lookup=500)).scan(sample, allow_upload=True)
    assert r["status"] == "failed" and r["verdict"] is None


def test_large_file_is_not_uploaded(tmp_path, monkeypatch):
    import app.security.virustotal as vt

    p = tmp_path / "big.bin"
    p.write_bytes(b"x")
    monkeypatch.setattr(vt, "PUBLIC_UPLOAD_LIMIT", 0)
    fake = FakeVT(known=None)
    assert client(fake).scan(p, allow_upload=True)["status"] == "too_large"
    assert ("POST", "/api/v3/files") not in fake.calls
    assert PUBLIC_UPLOAD_LIMIT == 32 * 1024 * 1024


def test_api_endpoint_scans_and_deletes_temp(tmp_path, monkeypatch):
    cfg = Settings()
    cfg.network_checks_enabled = False
    cfg.rate_limit_per_minute = 0
    cfg.virustotal_api_key = "TEST_KEY"
    media = MediaService(tmp_path / "x", isolation="inline", tmp_dir=tmp_path)
    app = create_app(cfg, media_service=media)
    fake = FakeVT(known={"malicious": 0, "suspicious": 0, "undetected": 70, "harmless": 0})
    app.state.vt.__dict__["_client"] = httpx.Client(base_url="https://www.virustotal.com/api/v3",
                                                    headers={"x-apikey": "TEST_KEY"},
                                                    transport=httpx.MockTransport(fake))
    with TestClient(app) as c:
        r = c.post("/api/v1/file/scan", files={"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")},
                   data={"allow_upload": "false"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "done" and body["verdict"] == "clean" and body["allow_upload"] is False
        assert list((tmp_path / "qorgau_media").iterdir()) == []  # temp file removed
        assert c.get("/api/v1/health").json()["external_services"]["virustotal"] is True


def test_health_reports_virustotal_disabled(tmp_path):
    cfg = Settings()
    cfg.network_checks_enabled = False
    cfg.rate_limit_per_minute = 0
    cfg.virustotal_api_key = None
    media = MediaService(tmp_path / "x", isolation="inline", tmp_dir=tmp_path)
    with TestClient(create_app(cfg, media_service=media)) as c:
        assert c.get("/api/v1/health").json()["external_services"]["virustotal"] is False
