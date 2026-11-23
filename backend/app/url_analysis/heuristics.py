"""Explainable rule-based signals for a URL.

Every signal has a stable `id` (localised on the client), a severity and a
weight in [0, 1]. Weights are hand-set for the MVP (documented in
docs/technical_report.md); they are combined as 1 - prod(1 - w).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .brand import BrandFindings, analyse_brand
from .data_lists import ABUSED_TLDS
from .features import (
    is_shortener,
    is_user_content_host,
    query_findings,
    risky_extension,
    suspicious_keywords,
)
from .normalize import ParsedUrl

SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3}


@dataclass
class Signal:
    id: str
    severity: str  # info | low | medium | high
    weight: float  # contribution to rule score; negative = reassuring
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def lexical_signals(p: ParsedUrl, brand: BrandFindings | None = None) -> list[Signal]:
    brand = brand or analyse_brand(p)
    s: list[Signal] = []

    if p.is_ip:
        s.append(Signal("ip_host", "high", 0.6, {"ip": p.host, "obfuscated": p.ip_obfuscated}))
    if p.userinfo is not None:
        s.append(Signal("userinfo_in_url", "high", 0.55, {"shown_part": p.userinfo[:40]}))
    if brand.lookalike_brand:
        if brand.lookalike_kind == "homoglyph":
            s.append(Signal("homoglyph_brand", "high", 0.85,
                            {"brand": brand.lookalike_target, "host": p.host_unicode, "punycode": p.host}))
        else:
            s.append(Signal("typosquat_brand", "high", 0.7,
                            {"brand": brand.lookalike_target, "domain": p.registered_domain}))
    if brand.mixed_script:
        s.append(Signal("mixed_script", "high", 0.6, {"scripts": brand.scripts, "host": p.host_unicode}))
    elif brand.non_ascii or "xn--" in p.host:
        s.append(Signal("idn_domain", "low", 0.15, {"host": p.host_unicode, "punycode": p.host}))
    if brand.subdomain_brand:
        s.append(Signal("brand_in_subdomain", "high", 0.6,
                        {"brand": brand.subdomain_brand, "domain": p.registered_domain}))
    if brand.combo_brand:
        s.append(Signal("brand_in_domain", "medium", 0.45,
                        {"brand": brand.combo_brand, "domain": p.registered_domain}))
    if brand.path_brand and not brand.official_domain:
        s.append(Signal("brand_in_path", "medium", 0.3,
                        {"brand": brand.path_brand, "domain": p.registered_domain}))

    if is_shortener(p.host):
        s.append(Signal("url_shortener", "low", 0.2, {"host": p.host}))
    if is_user_content_host(p.host):
        s.append(Signal("user_content_hosting", "medium", 0.25, {"host": p.host}))
    tld = p.suffix.split(".")[-1] if p.suffix else ""
    if tld in ABUSED_TLDS:
        s.append(Signal("abused_tld", "low", 0.15, {"tld": tld}))

    sub_labels = [x for x in p.subdomain.split(".") if x and x != "www"] if p.subdomain else []
    if len(sub_labels) >= 3:
        s.append(Signal("many_subdomains", "medium", 0.25, {"count": len(sub_labels)}))
    hyphens = p.host_unicode.removeprefix("www.").count("-")
    if hyphens >= 3:
        s.append(Signal("many_hyphens", "low", 0.15, {"count": hyphens}))
    if len(p.canonical) > 120:
        s.append(Signal("long_url", "low", 0.1, {"length": len(p.canonical)}))

    kws = suspicious_keywords(p)
    if kws:
        w = min(0.12 * len(kws), 0.35)
        s.append(Signal("suspicious_keywords", "medium" if len(kws) >= 2 else "low", w, {"keywords": kws[:6]}))

    email_q, redirect_q, redirect_names = query_findings(p)
    if email_q:
        s.append(Signal("email_in_query", "medium", 0.3, {}))
    if redirect_q:
        s.append(Signal("open_redirect_param", "medium", 0.25, {"params": redirect_names[:3]}))
    if p.port is not None:
        s.append(Signal("nonstandard_port", "medium", 0.2, {"port": p.port}))
    if "//" in p.path:
        s.append(Signal("double_slash_path", "low", 0.1, {}))
    if p.canonical.count("%") >= 5:
        s.append(Signal("heavy_encoding", "low", 0.15, {"count": p.canonical.count("%")}))
    ext = risky_extension(p)
    if ext:
        s.append(Signal("risky_download", "high", 0.4, {"extension": ext}))
    if p.scheme == "http":
        # Absence of TLS means traffic is unencrypted; it is NOT proof of phishing.
        s.append(Signal("no_tls", "low", 0.05, {}))
    if brand.official_domain and not is_user_content_host(p.host):
        s.append(Signal("official_domain", "info", -1.0, {"domain": p.registered_domain}))
    return s


def rule_score(signals: list[Signal]) -> float:
    prod = 1.0
    for sig in signals:
        if sig.weight > 0:
            prod *= 1.0 - min(sig.weight, 0.99)
    return 1.0 - prod


def max_severity(signals: list[Signal]) -> str:
    best = "info"
    for sig in signals:
        if sig.weight > 0 and SEVERITY_ORDER[sig.severity] > SEVERITY_ORDER[best]:
            best = sig.severity
    return best
