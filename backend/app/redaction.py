"""Helpers that keep secrets out of logs and responses."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .url_analysis.data_lists import SECRET_PARAM_NAMES


def redact_url_for_log(url: str, max_path: int = 60) -> str:
    """Log-safe form: scheme://host/path... with ALL query values and fragment removed."""
    try:
        parts = urlsplit(url)
        host = parts.hostname or "?"
        if parts.port:
            host = f"{host}:{parts.port}"
        path = parts.path[:max_path] + ("…" if len(parts.path) > max_path else "")
        keys = [k for k, _ in parse_qsl(parts.query, keep_blank_values=True)]
        query = "&".join(f"{k[:30]}=***" for k in keys[:10])
        return urlunsplit((parts.scheme, host, path, query, ""))
    except ValueError:
        return "<unparsable-url>"


def redact_url_for_client(url: str, max_value: int = 64) -> str:
    """Client-facing form: secret-looking query values masked, long values truncated,
    credentials in the authority removed."""
    try:
        parts = urlsplit(url)
        netloc = parts.netloc.rsplit("@", 1)[-1]
        q = []
        for k, v in parse_qsl(parts.query, keep_blank_values=True):
            if k.lower() in SECRET_PARAM_NAMES:
                v = "***"
            elif len(v) > max_value:
                v = v[:max_value] + "…"
            q.append((k, v))
        return urlunsplit((parts.scheme, netloc, parts.path, urlencode(q, safe="/:@*…"), ""))
    except ValueError:
        return "<unparsable-url>"
