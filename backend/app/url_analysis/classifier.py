"""Loads the scikit-learn URL classifier exported by ml/url_classifier/train.py."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from .features import FEATURE_NAMES, extract_features
from .normalize import ParsedUrl

log = logging.getLogger("qorgau.url_model")


class UrlClassifier:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._bundle: dict[str, Any] | None = None
        self.status = "not_loaded"
        self.error: str | None = None

    def load(self) -> None:
        with self._lock:
            if self._bundle is not None:
                return
            if not self.path.exists():
                self.status, self.error = "missing", f"Model file not found: {self.path.name}"
                log.warning("URL model missing at %s", self.path)
                return
            try:
                bundle = joblib.load(self.path)
                if bundle.get("feature_names") != FEATURE_NAMES:
                    raise ValueError("Feature list of the saved model differs from the code")
                self._bundle = bundle
                self.status, self.error = "loaded", None
                log.info("URL model loaded: %s", bundle.get("version"))
            except Exception as exc:  # corrupted file, version mismatch, ...
                self.status, self.error = "error", f"{type(exc).__name__}: {exc}"
                log.error("Failed to load URL model: %s", self.error)

    @property
    def available(self) -> bool:
        if self._bundle is None and self.status == "not_loaded":
            self.load()
        return self._bundle is not None

    def info(self) -> dict[str, Any]:
        b = self._bundle or {}
        return {
            "status": self.status if self._bundle or self.status != "not_loaded" else "not_loaded",
            "version": b.get("version"),
            "type": b.get("model_type"),
            "trained_at": b.get("trained_at"),
            "test_metrics": b.get("test_metrics"),
            "error": self.error,
        }

    def predict_proba(self, p: ParsedUrl) -> float | None:
        if not self.available:
            return None
        f = extract_features(p)
        x = np.array([[f[k] for k in FEATURE_NAMES]], dtype=float)
        return float(self._bundle["model"].predict_proba(x)[0, 1])
