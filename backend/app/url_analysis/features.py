"""Lexical feature extraction for the phishing URL classifier.

Shared by training (ml/url_classifier/train.py) and online inference.
Only the URL string is used: no network requests, no page content.

Deliberately EXCLUDED features (dataset artefacts, see docs/technical_report.md):
  * scheme (http/https) - HTTPS is not evidence of safety, and in PhiUSIIL all
    legitimate URLs are https, so the feature would leak the label;
  * presence of "www." - same artefact in PhiUSIIL.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, unquote

from .brand import BrandFindings, analyse_brand
from .data_lists import (
    ABUSED_TLDS,
    REDIRECT_PARAM_NAMES,
    RISKY_FILE_EXTENSIONS,
    SUSPICIOUS_KEYWORDS,
    URL_SHORTENERS,
    USER_CONTENT_EXACT_HOSTS,
    USER_CONTENT_HOSTS,
)
from .normalize import ParsedUrl
from .text_utils import longest_repeat_run, shannon_entropy

FEATURE_NAMES: list[str] = [
    "url_len", "host_len", "path_len", "query_len", "n_subdomain_levels", "n_dots_host",
    "n_hyphens_host", "n_digits_host", "host_digit_ratio", "url_digit_ratio",
    "n_special_url", "n_pct_encoded", "has_at", "is_ip", "has_port", "is_idn",
    "mixed_script", "n_query_params", "path_depth", "has_double_slash_path",
    "host_entropy", "path_entropy", "suspicious_kw_count", "brand_lookalike",
    "brand_in_domain_unofficial", "brand_in_subdomain", "brand_in_path",
    "official_brand_domain", "abused_tld", "user_content_host", "shortener",
    "risky_extension", "email_in_query", "redirect_param_url", "longest_repeat",
    "domain_label_len", "max_consonant_run", "tld_len", "script_ext_path",
]

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_SPECIAL = set("@~%=&_+!*,;$")
_CONSONANT_RUN = re.compile(r"[bcdfghjklmnpqrstvwxz]+")


def _host_matches(host: str, suffixes: set[str]) -> bool:
    return any(host == s or host.endswith("." + s) for s in suffixes)


def is_user_content_host(host: str) -> bool:
    h = host[4:] if host.startswith("www.") else host
    return h in USER_CONTENT_EXACT_HOSTS or _host_matches(h, USER_CONTENT_HOSTS)


def is_shortener(host: str) -> bool:
    h = host[4:] if host.startswith("www.") else host
    return h in URL_SHORTENERS


def suspicious_keywords(p: ParsedUrl) -> list[str]:
    hay = (p.host_no_www + " " + unquote(p.path) + " " + unquote(p.query)).lower()
    return [kw for kw in SUSPICIOUS_KEYWORDS if kw in hay]


def query_findings(p: ParsedUrl) -> tuple[bool, bool, list[str]]:
    """Return (email_in_query, redirect_param_with_url, redirect_param_names)."""
    email = bool(_EMAIL_RE.search(unquote(p.query)))
    redirect_names: list[str] = []
    for k, v in parse_qsl(p.query, keep_blank_values=True):
        if k.lower() in REDIRECT_PARAM_NAMES and re.match(r"^(https?:)?//|^www\.", unquote(v).strip(), re.I):
            redirect_names.append(k)
    return email, bool(redirect_names), redirect_names


def risky_extension(p: ParsedUrl) -> str | None:
    path = p.path.lower()
    for ext in RISKY_FILE_EXTENSIONS:
        if path.endswith(ext):
            return ext
    return None


def extract_features(p: ParsedUrl, brand: BrandFindings | None = None) -> dict[str, float]:
    brand = brand or analyse_brand(p)
    host = p.host_no_www
    url = p.canonical
    sub_levels = 0
    if p.subdomain:
        sub_labels = [s for s in p.subdomain.split(".") if s]
        if sub_labels and sub_labels[0] == "www":
            sub_labels = sub_labels[1:]
        sub_levels = len(sub_labels)
    n_digits_host = sum(c.isdigit() for c in host)
    n_digits_url = sum(c.isdigit() for c in url)
    path_segments = [s for s in p.path.split("/") if s]
    email_q, redirect_q, _ = query_findings(p)
    consonant_runs = [len(m) for m in _CONSONANT_RUN.findall(p.domain_label.lower())] or [0]
    last_seg = path_segments[-1].lower() if path_segments else ""

    feats = {
        "url_len": len(url),
        "host_len": len(host),
        "path_len": len(p.path),
        "query_len": len(p.query),
        "n_subdomain_levels": sub_levels,
        "n_dots_host": host.count("."),
        "n_hyphens_host": host.count("-"),
        "n_digits_host": n_digits_host,
        "host_digit_ratio": n_digits_host / max(len(host), 1),
        "url_digit_ratio": n_digits_url / max(len(url), 1),
        "n_special_url": sum(c in _SPECIAL for c in url),
        "n_pct_encoded": url.count("%"),
        "has_at": float(p.userinfo is not None or "@" in p.path),
        "is_ip": float(p.is_ip),
        "has_port": float(p.port is not None),
        "is_idn": float("xn--" in p.host or brand.non_ascii),
        "mixed_script": float(brand.mixed_script),
        "n_query_params": len(parse_qsl(p.query, keep_blank_values=True)),
        "path_depth": len(path_segments),
        "has_double_slash_path": float("//" in p.path),
        "host_entropy": shannon_entropy(host),
        "path_entropy": shannon_entropy(p.path),
        "suspicious_kw_count": len(suspicious_keywords(p)),
        "brand_lookalike": float(brand.lookalike_brand is not None),
        "brand_in_domain_unofficial": float(brand.combo_brand is not None),
        "brand_in_subdomain": float(brand.subdomain_brand is not None),
        "brand_in_path": float(brand.path_brand is not None),
        "official_brand_domain": float(brand.official_domain),
        "abused_tld": float(p.suffix.split(".")[-1] in ABUSED_TLDS if p.suffix else 0.0),
        "user_content_host": float(is_user_content_host(p.host)),
        "shortener": float(is_shortener(p.host)),
        "risky_extension": float(risky_extension(p) is not None),
        "email_in_query": float(email_q),
        "redirect_param_url": float(redirect_q),
        "longest_repeat": longest_repeat_run(url),
        "domain_label_len": len(p.domain_label),
        "max_consonant_run": max(consonant_runs),
        "tld_len": len(p.suffix),
        "script_ext_path": float(last_seg.endswith((".php", ".html", ".htm", ".asp", ".aspx", ".cgi"))),
    }
    return {k: float(feats[k]) for k in FEATURE_NAMES}


def feature_vector(p: ParsedUrl) -> list[float]:
    f = extract_features(p)
    return [f[k] for k in FEATURE_NAMES]
