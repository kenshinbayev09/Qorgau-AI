"""Локальный inference предобученного детектора дипфейков (PyTorch, transformers).

Модель: buildborderless/CommunityForensics-DeepfakeDet-ViT (MIT). Один выход —
сигмоида = вероятность, что изображение сгенерировано/подделано. Предобработку
(размер, обрезка) берём из preprocessor_config.json самой модели.

Реализовано в проекте: проверка и целостность весов, загрузка, батчевый inference,
вычисление P(подделка). Сами веса обучены автором модели (см. docs/models_and_datasets.md).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from PIL import Image

log = logging.getLogger("qorgau.deepfake")

MODEL_NAME = "buildborderless/CommunityForensics-DeepfakeDet-ViT"
MODEL_LICENSE = "mit"
MODEL_ARCH = "ViT-S/16 (384), CommunityForensics"
REQUIRED_FILES = ("config.json", "model.safetensors", "preprocessor_config.json")


def weights_present(model_dir: Path) -> bool:
    return all((Path(model_dir) / f).exists() for f in REQUIRED_FILES)


def static_info(model_dir: Path) -> dict[str, Any]:
    """Метаданные модели без импорта torch (дешёво, используется в /health)."""
    model_dir = Path(model_dir)
    info: dict[str, Any] = {"name": MODEL_NAME, "license": MODEL_LICENSE, "architecture": MODEL_ARCH,
                            "status": "not_connected", "version": None}
    if not weights_present(model_dir):
        info["error"] = "weights_missing"
        return info
    manifest = model_dir / "qorgau_manifest.json"
    if manifest.exists():
        try:
            info["version"] = json.loads(manifest.read_text())["revision"][:12]
        except (ValueError, KeyError):
            pass
    info["status"] = "configured"
    return info


class DeepfakeDetector:
    def __init__(self, model_dir: Path, threads: int = 2):
        self.model_dir = Path(model_dir)
        self.threads = threads
        self.model = None
        self.processor = None
        self.status = "not_loaded"
        self.error: str | None = None
        self.fake_indices: list[int] = []
        self.single_logit = False

    def load(self) -> None:
        if self.model is not None:
            return
        if not weights_present(self.model_dir):
            self.status, self.error = "not_connected", "weights_missing"
            return
        try:
            import torch
            from transformers import AutoImageProcessor, AutoModelForImageClassification

            torch.set_num_threads(max(1, self.threads))
            processor = AutoImageProcessor.from_pretrained(str(self.model_dir), local_files_only=True)
            model = AutoModelForImageClassification.from_pretrained(str(self.model_dir), local_files_only=True)
            model.eval()
            self.single_logit = model.config.num_labels == 1
            if not self.single_logit:
                labels = {int(k): str(v).lower() for k, v in (model.config.id2label or {}).items()}
                self.fake_indices = [i for i, n in labels.items() if any(k in n for k in ("fake", "deepfake", "ai"))]
                if not self.fake_indices:
                    raise ValueError(f"Unexpected label set {labels}")
            self.processor = processor
            self.model = model
            self.status, self.error = "loaded", None
            log.info("Deepfake model loaded from %s", self.model_dir)
        except Exception as exc:
            self.model = None
            self.status, self.error = "error", f"{type(exc).__name__}: {str(exc)[:200]}"
            log.error("Deepfake model failed to load: %s", self.error)

    def predict(self, images: list[Image.Image], batch_size: int = 8) -> list[float]:
        """Вероятность подделки (0..1) для каждого изображения."""
        if self.model is None:
            raise RuntimeError("model_not_loaded")
        import torch

        scores: list[float] = []
        with torch.inference_mode():
            for i in range(0, len(images), batch_size):
                batch = [im.convert("RGB") for im in images[i:i + batch_size]]
                inputs = self.processor(images=batch, return_tensors="pt")
                logits = self.model(**inputs).logits
                if self.single_logit:
                    probs = torch.sigmoid(logits[:, 0])
                else:
                    probs = torch.softmax(logits, dim=-1)[:, self.fake_indices].sum(dim=-1)
                scores.extend(float(p) for p in probs)
        return scores
