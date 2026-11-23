"""Optional Google Safe Browsing v4 Lookup API client.

Enabled only when GOOGLE_SAFE_BROWSING_API_KEY is set on the server. When
enabled, the URL being checked is sent to Google; the app discloses this on the
privacy screen (the /health endpoint reports whether it is enabled).
"""

from __future__ import annotations

import logging

import httpx

log = logging.getLogger("qorgau.reputation")
ENDPOINT = "https://safebrowsing.googleapis.com/v4/threatMatches:find"


class SafeBrowsingClient:
    def __init__(self, api_key: str | None, timeout: float = 4.0):
        self.api_key = api_key
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def lookup(self, url: str) -> dict:
        """Return {"status": "done"|"unavailable"|"failed", "matches": [...]}."""
        if not self.enabled:
            return {"status": "unavailable", "reason": "not_configured", "matches": []}
        body = {
            "client": {"clientId": "qorgau-ai", "clientVersion": "0.1.0"},
            "threatInfo": {
                "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE",
                                "POTENTIALLY_HARMFUL_APPLICATION"],
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": url}],
            },
        }
        try:
            r = httpx.post(ENDPOINT, params={"key": self.api_key}, json=body, timeout=self.timeout)
            r.raise_for_status()
            matches = [m.get("threatType") for m in r.json().get("matches", [])]
            return {"status": "done", "matches": matches}
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("Safe Browsing lookup failed: %s", type(exc).__name__)
            return {"status": "failed", "reason": type(exc).__name__, "matches": []}
