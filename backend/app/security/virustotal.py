"""Проверка файла через публичный API VirusTotal (v3).

Порядок работы (важно для приватности):
  1. Считаем SHA-256 файла на сервере.
  2. Спрашиваем VirusTotal только по хэшу (GET /files/{sha256}). Сам файл не уходит.
  3. Файл отправляем, ТОЛЬКО если пользователь явно разрешил (allow_upload=True)
     и файл не больше 32 МБ (лимит публичного API).

Важно: загруженные в публичный VirusTotal файлы становятся доступны
исследователям безопасности. Об этом пользователь предупреждён на экране согласия.
Результат — это мнение антивирусных движков, а не гарантия безопасности.
"""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger("qorgau.virustotal")

VT_BASE = "https://www.virustotal.com/api/v3"
PUBLIC_UPLOAD_LIMIT = 32 * 1024 * 1024  # публичный API: до 32 МБ


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verdict_for(stats: dict[str, int]) -> str:
    malicious = stats.get("malicious", 0)
    suspicious = stats.get("suspicious", 0)
    if malicious >= 3:
        return "malicious"
    if malicious >= 1 or suspicious >= 1:
        return "suspicious"
    return "clean"


class VirusTotalClient:
    def __init__(
        self,
        api_key: str | None,
        *,
        transport: httpx.BaseTransport | None = None,
        poll_interval: float = 3.0,
        poll_timeout: float = 90.0,
    ):
        self.api_key = api_key
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout
        self._client = httpx.Client(
            base_url=VT_BASE,
            headers={"x-apikey": api_key or ""},
            timeout=20.0,
            transport=transport,
        )

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _result(self, status: str, sha: str, **extra: Any) -> dict[str, Any]:
        out: dict[str, Any] = {
            "status": status,
            "sha256": sha,
            "permalink": f"https://www.virustotal.com/gui/file/{sha}",
            "stats": None,
            "verdict": None,
            "source": None,
            "reason": None,
        }
        out.update(extra)
        return out

    def scan(self, path: Path, *, allow_upload: bool) -> dict[str, Any]:
        sha = sha256_of(path)
        if not self.enabled:
            return self._result("disabled", sha, reason="not_configured")

        # 1. Только хэш
        try:
            r = self._client.get(f"/files/{sha}")
        except httpx.HTTPError as exc:
            log.warning("VirusTotal lookup failed: %s", type(exc).__name__)
            return self._result("failed", sha, reason="network")

        if r.status_code == 200:
            stats = r.json()["data"]["attributes"].get("last_analysis_stats", {})
            return self._result("done", sha, stats=stats, verdict=verdict_for(stats), source="known")
        if r.status_code == 429:
            return self._result("rate_limited", sha)
        if r.status_code not in (404,):
            return self._result("failed", sha, reason=f"http_{r.status_code}")

        # 2. Файла нет в базе: нужна загрузка
        if not allow_upload:
            return self._result("upload_required", sha)
        if path.stat().st_size > PUBLIC_UPLOAD_LIMIT:
            return self._result("too_large", sha)
        return self._upload_and_wait(path, sha)

    def _upload_and_wait(self, path: Path, sha: str) -> dict[str, Any]:
        try:
            with open(path, "rb") as fh:
                r = self._client.post("/files", files={"file": (path.name, fh, "application/octet-stream")})
        except httpx.HTTPError:
            return self._result("failed", sha, reason="network")
        if r.status_code == 429:
            return self._result("rate_limited", sha)
        if r.status_code >= 400:
            return self._result("failed", sha, reason=f"http_{r.status_code}")
        analysis_id = r.json()["data"]["id"]

        deadline = time.monotonic() + self.poll_timeout
        while time.monotonic() < deadline:
            time.sleep(self.poll_interval)
            try:
                a = self._client.get(f"/analyses/{analysis_id}")
            except httpx.HTTPError:
                return self._result("failed", sha, reason="network")
            if a.status_code == 429:
                return self._result("rate_limited", sha)
            if a.status_code >= 400:
                return self._result("failed", sha, reason=f"http_{a.status_code}")
            attrs = a.json()["data"]["attributes"]
            if attrs.get("status") == "completed":
                stats = attrs.get("stats", {})
                return self._result("done", sha, stats=stats, verdict=verdict_for(stats), source="uploaded")
        return self._result("timeout", sha)
