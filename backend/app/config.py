"""Runtime configuration from environment variables (see backend/.env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (KEY=VALUE lines); real environment wins."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv(BACKEND_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass
class Settings:
    url_model_path: Path = field(default_factory=lambda: Path(os.environ.get(
        "URL_MODEL_PATH", BACKEND_DIR / "models" / "url_classifier.joblib")))
    deepfake_model_dir: Path = field(default_factory=lambda: Path(os.environ.get(
        "DEEPFAKE_MODEL_DIR", REPO_DIR / "ml" / "deepfake" / "weights" / "community-forensics-vit")))
    network_checks_enabled: bool = field(default_factory=lambda: _bool("NETWORK_CHECKS_ENABLED", True))
    fetch_total_timeout: float = field(default_factory=lambda: _float("FETCH_TOTAL_TIMEOUT_S", 8.0))
    fetch_max_redirects: int = field(default_factory=lambda: _int("FETCH_MAX_REDIRECTS", 5))
    max_upload_mb: int = field(default_factory=lambda: _int("MAX_UPLOAD_MB", 50))
    max_video_seconds: int = field(default_factory=lambda: _int("MAX_VIDEO_SECONDS", 60))
    max_video_frames: int = field(default_factory=lambda: _int("MAX_VIDEO_FRAMES", 16))
    max_image_pixels: int = field(default_factory=lambda: _int("MAX_IMAGE_PIXELS", 40_000_000))
    media_timeout_s: int = field(default_factory=lambda: _int("MEDIA_TIMEOUT_S", 90))
    media_isolation: str = field(default_factory=lambda: os.environ.get("MEDIA_ISOLATION", "process"))
    media_worker_memory_mb: int = field(default_factory=lambda: _int("MEDIA_WORKER_MEMORY_MB", 3072))
    torch_threads: int = field(default_factory=lambda: _int("TORCH_THREADS", 2))
    # Optional external services (keys stay on the server only)
    safe_browsing_api_key: str | None = field(default_factory=lambda: os.environ.get("GOOGLE_SAFE_BROWSING_API_KEY") or None)
    anthropic_api_key: str | None = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY") or None)
    virustotal_api_key: str | None = field(default_factory=lambda: os.environ.get("VIRUSTOTAL_API_KEY") or None)
    llm_model: str = field(default_factory=lambda: os.environ.get("LLM_MODEL", "claude-opus-5-5"))
    cors_origins: list[str] = field(default_factory=lambda: [o for o in os.environ.get("CORS_ORIGINS", "").split(",") if o])
    rate_limit_per_minute: int = field(default_factory=lambda: _int("RATE_LIMIT_PER_MINUTE", 60))


settings = Settings()
