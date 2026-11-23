"""URL check orchestration: lexical rules + ML model + safe network analysis.

Scoring (documented in docs/technical_report.md):
  rules  = 1 - prod(1 - w_i) over positive signal weights
  score  = 0.5 * p_model + 0.5 * rules            (model available)
         = rules                                   (model unavailable)
  floors: any "high" signal -> score >= 0.65; any "medium" -> score >= 0.35
  official domain (and no high signal) -> score <= 0.30
  reputation match (Safe Browsing) -> score >= 0.95
  category: <0.35 low, <0.65 suspicious, >=0.65 high;
            "insufficient" when the model is unavailable and no rule fired.
The score is a model estimate, not a probability of harm.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from ..net.safe_fetch import FetchResult, SafeFetcher, html_signals
from ..redaction import redact_url_for_client, redact_url_for_log
from .brand import analyse_brand
from .classifier import UrlClassifier
from .heuristics import Signal, lexical_signals, rule_score
from .normalize import ParsedUrl, UrlValidationError, parse_url, registered_domain_of
from .reputation import SafeBrowsingClient

log = logging.getLogger("qorgau.url")

LOW_MAX, SUSPICIOUS_MAX = 0.35, 0.65


def category_for(score: float) -> str:
    if score < LOW_MAX:
        return "low"
    if score < SUSPICIOUS_MAX:
        return "suspicious"
    return "high"


def network_signals(p: ParsedUrl, fr: FetchResult) -> list[Signal]:
    s: list[Signal] = []
    hops = fr.hops
    redirects = max(0, len(hops) - 1)
    if fr.error_code == "blocked_address":
        blocked = hops[-1]
        if len(hops) > 1:
            s.append(Signal("redirect_to_internal", "high", 0.6, {"reason": blocked.blocked_reason}))
        else:
            s.append(Signal("internal_address", "high", 0.5, {"reason": blocked.blocked_reason}))
    if fr.error_code and fr.error_code.startswith("invalid_redirect_target"):
        s.append(Signal("invalid_redirect", "medium", 0.3, {"code": fr.error_code}))
    if fr.error_code == "tls_certificate_invalid":
        s.append(Signal("tls_invalid", "medium", 0.3, {}))
    if fr.error_code == "dns_failed":
        s.append(Signal("domain_not_resolving", "low", 0.15, {}))
    if fr.error_code == "too_many_redirects":
        s.append(Signal("too_many_redirects", "medium", 0.3, {"count": redirects}))
    if redirects >= 3:
        s.append(Signal("long_redirect_chain", "low", 0.15, {"count": redirects}))
    if fr.final_host and redirects:
        start_rd = p.registered_domain
        final_rd = registered_domain_of(_ascii_host(fr.final_host))
        if final_rd != start_rd:
            s.append(Signal("cross_domain_redirect", "medium", 0.2, {"from": start_rd, "to": final_rd}))
            if fr.final_url:
                try:
                    fp = parse_url(fr.final_url)
                    final_sigs = [x for x in lexical_signals(fp) if x.weight > 0 and x.id != "no_tls"]
                    fs = rule_score(final_sigs)
                    if fs >= 0.3:
                        s.append(Signal("risky_final_destination",
                                        "high" if fs >= 0.6 else "medium", round(0.8 * fs, 3),
                                        {"domain": final_rd, "signals": [x.id for x in final_sigs][:5]}))
                except UrlValidationError:
                    pass
    if fr.body_head and (fr.content_type or "").startswith(("text/html", "application/xhtml")):
        h = html_signals(fr.body_head)
        brand_official = analyse_brand(p).official_domain
        if h.get("password_field") and not brand_official:
            s.append(Signal("password_form", "medium", 0.3, {}))
        ext_forms = [a for a in h.get("external_form_actions", [])
                     if registered_domain_of(_ascii_host(_host_of(a))) not in (p.registered_domain, "")]
        if ext_forms:
            s.append(Signal("external_form_action", "medium", 0.3,
                            {"domains": sorted({registered_domain_of(_ascii_host(_host_of(a))) for a in ext_forms})[:3]}))
        if h.get("meta_refresh_target"):
            s.append(Signal("meta_refresh", "low", 0.1, {"target_host": _host_of(h["meta_refresh_target"])}))
    return s


def _host_of(url: str) -> str:
    try:
        from urllib.parse import urlsplit

        return urlsplit(url).hostname or ""
    except ValueError:
        return ""


def _ascii_host(host: str) -> str:
    try:
        return host.encode("idna").decode("ascii") if not host.isascii() else host
    except UnicodeError:
        return host


def advice_for(category: str, signal_ids: set[str]) -> list[str]:
    base = {
        "low": ["verify_sender", "https_not_guarantee"],
        "suspicious": ["dont_enter_data", "use_official_app", "verify_sender"],
        "high": ["dont_open", "dont_enter_data", "report_link", "if_entered_act"],
        "insufficient": ["verify_sender", "use_official_app"],
    }[category]
    extra = []
    if signal_ids & {"homoglyph_brand", "mixed_script", "typosquat_brand", "idn_domain"}:
        extra.append("check_letters")
    if "url_shortener" in signal_ids:
        extra.append("shortener_hidden")
    if "risky_download" in signal_ids:
        extra.append("dont_install")
    if "password_form" in signal_ids:
        extra.append("password_only_official")
    return extra + [a for a in base if a not in extra]


class UrlCheckService:
    def __init__(self, classifier: UrlClassifier, fetcher: SafeFetcher | None,
                 reputation: SafeBrowsingClient, network_enabled: bool = True):
        self.classifier = classifier
        self.fetcher = fetcher
        self.reputation = reputation
        self.network_enabled = network_enabled and fetcher is not None

    def check(self, raw: str, *, network: bool = True) -> dict[str, Any]:
        t0 = time.monotonic()
        p = parse_url(raw)  # raises UrlValidationError -> 422 at the API layer
        log.info("url check host=%s target=%s", p.host, redact_url_for_log(f"{p.scheme}://{p.host}{p.path}"))
        brand = analyse_brand(p)
        signals = lexical_signals(p, brand)
        checks: list[dict[str, Any]] = [
            {"id": "url_structure", "status": "done"},
            {"id": "lookalike_domains", "status": "done"},
        ]

        p_model = None
        if self.classifier.available:
            p_model = self.classifier.predict_proba(p)
            checks.append({"id": "ml_model", "status": "done"})
        else:
            checks.append({"id": "ml_model", "status": "unavailable", "detail": self.classifier.status})

        fetch_dict = None
        if not self.network_enabled:
            checks.append({"id": "redirects", "status": "disabled"})
        elif not network:
            checks.append({"id": "redirects", "status": "skipped"})
        else:
            fr = self.fetcher.fetch(f"{p.scheme}://{p.host if ':' not in p.host else '[' + p.host + ']'}"
                                    f"{':' + str(p.port) if p.port else ''}{p.path or '/'}"
                                    f"{'?' + p.query if p.query else ''}")
            fetch_dict = fr.to_dict()
            signals += network_signals(p, fr)
            if fr.error_code in (None,):
                checks.append({"id": "redirects", "status": "done", "detail": f"{max(0, len(fr.hops) - 1)}"})
                checks.append({"id": "page_markup", "status": "done" if fr.body_head else "unavailable"})
            elif fr.error_code in ("blocked_address", "blocked_port", "too_many_redirects", "redirect_loop") or \
                    fr.error_code.startswith("invalid_redirect_target"):
                checks.append({"id": "redirects", "status": "stopped", "detail": fr.error_code})
            else:
                checks.append({"id": "redirects", "status": "failed", "detail": fr.error_code})

        rep = self.reputation.lookup(f"{p.scheme}://{p.host}{p.path or '/'}") if self.reputation.enabled and network \
            else {"status": "unavailable", "reason": "not_configured" if not self.reputation.enabled else "skipped"}
        checks.append({"id": "reputation", "status": rep["status"], "detail": rep.get("reason")})
        if rep.get("matches"):
            signals.append(Signal("reputation_match", "high", 0.95, {"threats": rep["matches"]}))

        positive = [s for s in signals if s.weight > 0]
        meaningful = [s for s in positive if s.id != "no_tls"]
        rules = rule_score(positive)
        official = any(s.id == "official_domain" for s in signals)
        has_high = any(s.severity == "high" for s in positive)
        has_medium = any(s.severity == "medium" for s in positive)

        if p_model is None and not meaningful and not official:
            score, category = None, "insufficient"
        else:
            score = rules if p_model is None else 0.5 * p_model + 0.5 * rules
            if has_high:
                score = max(score, SUSPICIOUS_MAX)
            elif has_medium:
                score = max(score, LOW_MAX)
            if official and not has_high:
                score = min(score, 0.30)
            if rep.get("matches"):
                score = max(score, 0.95)
            score = round(min(max(score, 0.0), 1.0), 3)
            category = category_for(score)

        signals.sort(key=lambda s: (-{"high": 3, "medium": 2, "low": 1, "info": 0}[s.severity], -s.weight))
        return {
            "kind": "url",
            "input": redact_url_for_client(raw if p.had_scheme else f"{p.scheme}://{raw.strip()}"),
            "normalized": {
                "scheme": p.scheme,
                "host": p.host_unicode,
                "host_ascii": p.host,
                "registered_domain": p.registered_domain,
                "is_ip": p.is_ip,
                "path": (p.path[:120] + "…") if len(p.path) > 120 else p.path,
                "has_query": bool(p.query),
            },
            "category": category,
            "score": score,
            "score_components": {"model": None if p_model is None else round(p_model, 4), "rules": round(rules, 4)},
            "model": self.classifier.info(),
            "signals": [s.to_dict() for s in signals],
            "checks": checks,
            "redirects": fetch_dict,
            "advice": advice_for(category, {s.id for s in signals}),
            "disclaimer": "model_estimate",
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": int((time.monotonic() - t0) * 1000),
        }
