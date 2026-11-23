import logging

from conftest import URL_MODEL, requires_url_model

from app.net.safe_fetch import FetchResult, Hop
from app.redaction import redact_url_for_log
from app.url_analysis.classifier import UrlClassifier
from app.url_analysis.reputation import SafeBrowsingClient
from app.url_analysis.service import UrlCheckService


class FakeFetcher:
    def __init__(self, result: FetchResult):
        self.result = result
        self.calls = 0

    def fetch(self, url, **kw):
        self.calls += 1
        return self.result


def service(model_path=URL_MODEL, fetch_result=None, network=True):
    return UrlCheckService(UrlClassifier(model_path), FakeFetcher(fetch_result or FetchResult()) if network else None,
                           SafeBrowsingClient(None), network_enabled=network)


def test_model_missing_and_no_signals_gives_insufficient(tmp_path):
    r = service(tmp_path / "nope.joblib", network=False).check("https://plain-bakery-almaty.kz/menu")
    assert r["category"] == "insufficient" and r["score"] is None
    assert {"id": "ml_model", "status": "unavailable", "detail": "missing"} in r["checks"]


def test_model_missing_still_reports_rule_signals(tmp_path):
    r = service(tmp_path / "nope.joblib", network=False).check("http://kaspi.kz.secure-login.xyz/verify")
    assert r["category"] == "high" and r["score_components"]["model"] is None


def test_corrupted_model_file_reports_error(tmp_path):
    bad = tmp_path / "bad.joblib"
    bad.write_bytes(b"not a joblib file")
    svc = service(bad, network=False)
    r = svc.check("https://example.org/")
    assert svc.classifier.status == "error"
    assert any(c["id"] == "ml_model" and c["detail"] == "error" for c in r["checks"])


@requires_url_model
def test_model_is_used_and_score_explained():
    r = service(network=False).check("https://paypa1-secure-login.top/verify/account.php?email=a@b.c")
    assert r["category"] == "high" and 0 <= r["score_components"]["model"] <= 1
    assert r["model"]["status"] == "loaded" and r["model"]["version"]
    assert r["disclaimer"] == "model_estimate"


@requires_url_model
def test_official_domain_capped_low():
    r = service(network=False).check("https://kaspi.kz/shop/c/smartphones/")
    assert r["category"] == "low" and r["score"] <= 0.30


def test_network_checks_disabled_and_skipped(tmp_path):
    r = service(tmp_path / "x", network=False).check("https://example.org")
    assert {"id": "redirects", "status": "disabled"} in r["checks"]
    svc = service(tmp_path / "x")
    r = svc.check("https://example.org", network=False)
    assert {"id": "redirects", "status": "skipped"} in r["checks"] and svc.fetcher.calls == 0


def test_redirect_chain_signals(tmp_path):
    fr = FetchResult(hops=[Hop(url="https://bit.ly/x", host="bit.ly", status=301),
                           Hop(url="https://kaspi-bonus.top/login", host="kaspi-bonus.top", status=200)],
                     final_url="https://kaspi-bonus.top/login", final_host="kaspi-bonus.top", final_status=200,
                     content_type="text/html", body_head=b'<form action="https://collector.example.net/p">'
                                                         b'<input type="password" name="p"></form>')
    r = service(tmp_path / "x", fr).check("https://bit.ly/x")
    got = {s["id"] for s in r["signals"]}
    assert {"cross_domain_redirect", "risky_final_destination", "password_form", "external_form_action"} <= got
    assert r["category"] in ("suspicious", "high")


def test_redirect_to_internal_address_signal(tmp_path):
    fr = FetchResult(hops=[Hop(url="https://a.example.com/", host="a.example.com", status=302),
                           Hop(url="http://169.254.169.254/", host="169.254.169.254", blocked_reason="link_local")],
                     error_code="blocked_address")
    r = service(tmp_path / "x", fr).check("https://a.example.com/")
    assert "redirect_to_internal" in {s["id"] for s in r["signals"]}
    assert any(c["id"] == "redirects" and c["status"] == "stopped" for c in r["checks"])


def test_secrets_never_logged(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    service(tmp_path / "x", network=False).check("https://example.org/cb?token=SUPERSECRET&code=777")
    assert "SUPERSECRET" not in caplog.text and "777" not in caplog.text
    assert redact_url_for_log("https://u:pw@ex.com/p?token=abc&x=1#frag") == "https://ex.com/p?token=***&x=***"
