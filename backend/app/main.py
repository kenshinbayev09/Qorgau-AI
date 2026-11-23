"""Qorgau AI backend (FastAPI).

Run:  uvicorn app.main:app --host 0.0.0.0 --port 8000   (from backend/)
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .agent.agent import QorgauAgent
from .agent.explain import LlmExplainer
from .config import Settings, settings as default_settings
from .deepfake.analysis import Limits
from .deepfake.media import MediaError
from .deepfake.service import MediaService
from .demo import demo_media_result
from .net.safe_fetch import SafeFetcher
from .security.virustotal import VirusTotalClient
from .url_analysis.classifier import UrlClassifier
from .url_analysis.normalize import UrlValidationError
from .url_analysis.reputation import SafeBrowsingClient
from .url_analysis.service import UrlCheckService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("qorgau.api")
API_VERSION = "0.1.0"


class UrlCheckRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=4096)
    network: bool = True


class MediaUrlRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=4096)


class AgentRequest(BaseModel):
    text: str = Field("", max_length=8000)
    attached_result: dict[str, Any] | None = None
    lang: str = Field("ru", pattern="^(ru|kk|en)$")
    allow_network: bool = True
    use_llm: bool = False


def error(code: str, status: int, message: str = "") -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


class RateLimiter:
    """Tiny in-memory sliding-window limiter per client IP (single-process MVP)."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        if self.per_minute <= 0:
            return True
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.per_minute:
                return False
            q.append(now)
            return True


def create_app(cfg: Settings | None = None, *, fetcher: SafeFetcher | None = None,
               media_service: MediaService | None = None) -> FastAPI:
    cfg = cfg or default_settings
    fetcher = fetcher if fetcher is not None else (
        SafeFetcher(total_timeout=cfg.fetch_total_timeout, max_redirects=cfg.fetch_max_redirects)
        if cfg.network_checks_enabled else None)
    classifier = UrlClassifier(cfg.url_model_path)
    reputation = SafeBrowsingClient(cfg.safe_browsing_api_key)
    url_service = UrlCheckService(classifier, fetcher, reputation, cfg.network_checks_enabled)
    media = media_service or MediaService(
        cfg.deepfake_model_dir, isolation=cfg.media_isolation, threads=cfg.torch_threads,
        memory_mb=cfg.media_worker_memory_mb, timeout_s=cfg.media_timeout_s, max_upload_mb=cfg.max_upload_mb,
        limits=Limits(cfg.max_video_seconds, cfg.max_video_frames, cfg.max_image_pixels), fetcher=fetcher)
    explainer = LlmExplainer(cfg.anthropic_api_key, cfg.llm_model)
    vt = VirusTotalClient(cfg.virustotal_api_key)
    agent = QorgauAgent(url_service, media, explainer)
    limiter = RateLimiter(cfg.rate_limit_per_minute)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        classifier.load()
        yield
        media.shutdown()

    app = FastAPI(title="Qorgau AI API", version=API_VERSION, lifespan=lifespan)
    app.state.url_service, app.state.media, app.state.agent = url_service, media, agent
    app.state.vt = vt
    if cfg.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=cfg.cors_origins, allow_methods=["GET", "POST"],
                           allow_headers=["*"])

    @app.middleware("http")
    async def limit(request: Request, call_next):
        if request.url.path.startswith("/api/") and request.url.path != "/api/v1/health":
            ip = request.client.host if request.client else "unknown"
            if not limiter.allow(ip):
                return error("rate_limited", 429, "Too many requests")
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def on_validation(_: Request, exc: RequestValidationError):
        return error("invalid_request", 422, "Request body is invalid")

    @app.get("/api/v1/health")
    def health():
        return {
            "status": "ok",
            "version": API_VERSION,
            "url_model": classifier.info(),
            "deepfake_model": media.model_info(),
            "network_checks": cfg.network_checks_enabled,
            "external_services": {
                "safe_browsing": reputation.enabled,  # if true, checked URLs are sent to Google
                "llm_explanations": explainer.enabled,  # if true, sanitised results are sent to Anthropic
                "virustotal": vt.enabled,  # if true, file hashes (and files, if the user allows) go to VirusTotal
            },
            "limits": {"max_upload_mb": cfg.max_upload_mb, "max_video_seconds": cfg.max_video_seconds,
                       "max_video_frames": cfg.max_video_frames},
        }

    @app.post("/api/v1/url/check")
    def url_check(req: UrlCheckRequest):
        try:
            return url_service.check(req.url, network=req.network)
        except UrlValidationError as exc:
            return error(f"invalid_url:{exc.code}", 422, str(exc))

    @app.post("/api/v1/media/upload")
    def media_upload(file: UploadFile = File(...)):
        try:
            return media.analyse_upload(file.file)
        except MediaError as exc:
            return error(exc.code, exc.http_status, str(exc))
        finally:
            file.file.close()

    @app.post("/api/v1/media/url")
    def media_url(req: MediaUrlRequest):
        try:
            return media.analyse_url(req.url)
        except UrlValidationError as exc:
            return error(f"invalid_url:{exc.code}", 422, str(exc))
        except MediaError as exc:
            return error(exc.code, exc.http_status, str(exc))

    @app.post("/api/v1/file/scan")
    def file_scan(file: UploadFile = File(...), allow_upload: bool = Form(False)):
        """Проверка файла по хэшу в VirusTotal. Файл отправляется, только если allow_upload=true."""
        path = None
        try:
            path = media.save_upload(file.file)
            return vt.scan(path, allow_upload=allow_upload) | {"allow_upload": allow_upload}
        except MediaError as exc:
            return error(exc.code, exc.http_status, str(exc))
        finally:
            file.file.close()
            if path is not None:
                path.unlink(missing_ok=True)

    @app.get("/api/v1/demo/media")
    def demo_media():
        return demo_media_result()

    @app.post("/api/v1/agent/run")
    def agent_run(req: AgentRequest):
        return agent.run(req.text, req.attached_result, lang=req.lang, allow_network=req.allow_network,
                         use_llm=req.use_llm)

    return app


app = create_app()
