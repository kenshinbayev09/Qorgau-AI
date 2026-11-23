"""Media analysis service: temp-file handling, isolation and resource limits.

Isolation: analysis runs in a dedicated worker process (ProcessPoolExecutor,
1 worker) that loads the model once. A wall-clock timeout kills and restarts
the worker; a crash (e.g. memory limit) also restarts it. On Linux/macOS the
worker gets an address-space limit (RLIMIT_AS). Temporary files are always
deleted in `finally` blocks; originals are never stored.
"""

from __future__ import annotations

import concurrent.futures
import logging
import os
import sys
import tempfile
import threading
import time
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path
from typing import Any, BinaryIO

from ..net.safe_fetch import SafeFetcher
from ..url_analysis.data_lists import SOCIAL_MEDIA_HOSTS
from ..url_analysis.normalize import parse_url
from .analysis import Limits, analyse
from .detector import DeepfakeDetector, static_info, weights_present
from .media import MediaError, sniff

log = logging.getLogger("qorgau.media")

_worker_detector: DeepfakeDetector | None = None


def _worker_init(model_dir: str, threads: int, memory_mb: int) -> None:
    global _worker_detector
    if memory_mb and sys.platform != "win32":
        try:
            import resource

            limit = memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        except (ImportError, ValueError, OSError):
            pass
    _worker_detector = DeepfakeDetector(Path(model_dir), threads)


def _worker_run(path: str, kind: str, limits: Limits) -> dict[str, Any]:
    assert _worker_detector is not None
    try:
        return {"ok": True, "result": analyse(path, kind, _worker_detector, limits)}
    except MediaError as exc:
        return {"ok": False, "code": exc.code, "message": str(exc), "http_status": exc.http_status,
                "model_status": _worker_detector.status, "model_error": _worker_detector.error}


class MediaService:
    def __init__(self, model_dir: Path, *, isolation: str = "process", threads: int = 2,
                 memory_mb: int = 3072, timeout_s: int = 90, max_upload_mb: int = 50,
                 limits: Limits | None = None, fetcher: SafeFetcher | None = None,
                 tmp_dir: Path | None = None):
        self.model_dir = Path(model_dir)
        self.isolation = isolation
        self.threads = threads
        self.memory_mb = memory_mb
        self.timeout_s = timeout_s
        self.max_bytes = max_upload_mb * 1024 * 1024
        self.limits = limits or Limits()
        self.fetcher = fetcher
        self.tmp_dir = Path(tmp_dir or tempfile.gettempdir()) / "qorgau_media"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._pool: concurrent.futures.ProcessPoolExecutor | None = None
        self._inline_detector: DeepfakeDetector | None = None
        self._last_load_error: str | None = None

    # ---------- status ----------
    def model_info(self) -> dict[str, Any]:
        info = static_info(self.model_dir)
        if self._last_load_error and info["status"] == "configured":
            info["status"], info["error"] = "error", self._last_load_error
        return info

    @property
    def model_connected(self) -> bool:
        return weights_present(self.model_dir) and self._last_load_error is None

    # ---------- worker management ----------
    def _get_pool(self) -> concurrent.futures.ProcessPoolExecutor:
        if self._pool is None:
            self._pool = concurrent.futures.ProcessPoolExecutor(
                max_workers=1, initializer=_worker_init,
                initargs=(str(self.model_dir), self.threads, self.memory_mb))
        return self._pool

    def _kill_pool(self) -> None:
        pool, self._pool = self._pool, None
        if pool is None:
            return
        for proc in list(getattr(pool, "_processes", {}).values()):
            try:
                proc.kill()
            except Exception:
                pass
        pool.shutdown(wait=False, cancel_futures=True)

    def shutdown(self) -> None:
        self._kill_pool()

    def _run(self, path: str, kind: str) -> dict[str, Any]:
        if self.isolation == "inline":
            if self._inline_detector is None:
                self._inline_detector = DeepfakeDetector(self.model_dir, self.threads)
            try:
                return {"ok": True, "result": analyse(path, kind, self._inline_detector, self.limits)}
            except MediaError as exc:
                return {"ok": False, "code": exc.code, "message": str(exc), "http_status": exc.http_status,
                        "model_status": self._inline_detector.status, "model_error": self._inline_detector.error}
        with self._lock:  # one analysis at a time per worker
            fut = self._get_pool().submit(_worker_run, path, kind, self.limits)
            try:
                return fut.result(timeout=self.timeout_s)
            except concurrent.futures.TimeoutError:
                self._kill_pool()
                raise MediaError("timeout", "Media analysis timed out", 504)
            except BrokenProcessPool:
                self._kill_pool()
                raise MediaError("processing_failed", "Media worker crashed (resource limit?)", 500)

    # ---------- public API ----------
    def _ensure_model(self) -> None:
        if not weights_present(self.model_dir):
            raise MediaError("model_unavailable", "Deepfake model weights are not installed", 503)

    def save_upload(self, stream: BinaryIO) -> Path:
        fd, name = tempfile.mkstemp(prefix="up_", dir=self.tmp_dir)
        total = 0
        try:
            with os.fdopen(fd, "wb") as out:
                while chunk := stream.read(1024 * 1024):
                    total += len(chunk)
                    if total > self.max_bytes:
                        raise MediaError("too_large", f"File larger than {self.max_bytes // (1024 * 1024)} MB", 413)
                    out.write(chunk)
            if total == 0:
                raise MediaError("empty_file", "Empty file", 422)
            return Path(name)
        except BaseException:
            Path(name).unlink(missing_ok=True)
            raise

    def analyse_path(self, path: Path, source: str) -> dict[str, Any]:
        t0 = time.monotonic()
        with open(path, "rb") as f:
            head = f.read(64)
        fmt = sniff(head)
        self._ensure_model()
        out = self._run(str(path), fmt.kind)
        if not out["ok"]:
            if out["code"] == "model_unavailable":
                self._last_load_error = out.get("model_error")
            raise MediaError(out["code"], out["message"], out["http_status"])
        self._last_load_error = None
        res = out["result"]
        res.update({
            "kind": "media",
            "source": source,
            "format": fmt.fmt,
            "model": self.model_info() | {"status": "loaded"},
            "duration_ms": int((time.monotonic() - t0) * 1000),
            "demo": False,
        })
        res["stages"] = [{"id": "validate_format", "status": "done", "ms": 0}] + res["stages"]
        return res

    def analyse_upload(self, stream: BinaryIO) -> dict[str, Any]:
        self._ensure_model()
        path = self.save_upload(stream)
        try:
            return self.analyse_path(path, "upload")
        finally:
            path.unlink(missing_ok=True)

    def analyse_url(self, url: str) -> dict[str, Any]:
        p = parse_url(url)
        host = p.host_no_www
        if any(host == h or host.endswith("." + h) for h in SOCIAL_MEDIA_HOSTS):
            raise MediaError("social_page", "Links to social network pages cannot be analysed; upload the file", 422)
        self._ensure_model()
        if self.fetcher is None:
            raise MediaError("network_disabled", "Network access is disabled on the server", 503)
        fd, name = tempfile.mkstemp(prefix="dl_", dir=self.tmp_dir)
        path = Path(name)
        try:
            with os.fdopen(fd, "wb") as sink:
                fr = self.fetcher.fetch(url, max_bytes=self.max_bytes, sink=sink, fail_if_larger=True,
                                        accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm")
            if fr.error_code == "too_large":
                raise MediaError("too_large", "Remote file is too large", 413)
            if fr.error_code in ("blocked_address", "blocked_port"):
                raise MediaError("blocked_url", "This address is not allowed", 422)
            if fr.error_code == "timeout":
                raise MediaError("timeout", "Download timed out", 504)
            if fr.error_code:
                raise MediaError("download_failed", fr.error_code, 502)
            if fr.final_status is None or fr.final_status >= 400:
                raise MediaError("download_failed", f"HTTP {fr.final_status}", 502)
            ctype = fr.content_type or ""
            if ctype.startswith(("text/html", "application/xhtml")):
                raise MediaError("not_media_html", "The link leads to a web page, not a media file", 415)
            res = self.analyse_path(path, "url")
            res["source_host"] = p.host_unicode
            return res
        finally:
            path.unlink(missing_ok=True)
