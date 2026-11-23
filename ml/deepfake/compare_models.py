"""Сравнение предобученных детекторов дипфейков на одной и той же выборке.

Выборка: ml/data/deepfake_eval/{real,fake} (DeepFakeFace, seed 7).
Для каждой модели считаем ROC-AUC на полном изображении и на кропе лица
(кроп — тот же детектор лица, что в API; если лица нет, изображение пропускаем).

Запуск (из корня проекта):
    .venv\\Scripts\\python ml/deepfake/compare_models.py
Результат: ml/reports/model_comparison.json и .md
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from huggingface_hub import snapshot_download
from PIL import Image
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.deepfake.faces import crop_face, detect_faces  # noqa: E402

DATA = ROOT / "ml" / "data" / "deepfake_eval"
CAND = ROOT / "ml" / "deepfake" / "candidates"
REPORTS = ROOT / "ml" / "reports"

# (repo, revision или None, файлы для загрузки, лицензия)
MODELS = [
    ("prithivMLmods/Deep-Fake-Detector-v2-Model", "3a99ae26f52c7ac7c3a53103b6cf3a8b617f7093", "apache-2.0"),
    ("dima806/deepfake_vs_real_image_detection", None, "apache-2.0"),
    ("buildborderless/CommunityForensics-DeepfakeDet-ViT", None, "mit"),
    ("prithivMLmods/AI-vs-Deepfake-vs-Real-Siglip2", None, "apache-2.0"),
]
FILES = ["config.json", "preprocessor_config.json", "model.safetensors"]


def load(repo: str, revision: str | None):
    import torch
    from transformers import AutoImageProcessor, AutoModelForImageClassification

    local = snapshot_download(repo, revision=revision, allow_patterns=FILES, local_dir=CAND / repo.split("/")[1])
    proc = AutoImageProcessor.from_pretrained(local)
    model = AutoModelForImageClassification.from_pretrained(local).eval()
    return proc, model


def fake_score_fn(model):
    """Возвращает функцию: список PIL-изображений -> P(подделка) для каждого."""
    import torch

    labels = {int(k): str(v).lower() for k, v in model.config.id2label.items()} if model.config.id2label else {}
    single_logit = model.config.num_labels == 1

    def score(proc, images):
        inputs = proc(images=images, return_tensors="pt")
        with torch.inference_mode():
            logits = model(**inputs).logits
        if single_logit:  # одна метка: сигмоида = P(подделка)
            return torch.sigmoid(logits[:, 0]).tolist()
        probs = torch.softmax(logits, dim=-1)
        fake_idx = [i for i, name in labels.items() if any(k in name for k in ("fake", "deepfake", "ai"))]
        if not fake_idx:
            raise RuntimeError(f"Не нашёл метку подделки в {labels}")
        return probs[:, fake_idx].sum(dim=-1).tolist()

    return score


def run_model(repo: str, revision: str | None) -> dict:
    t0 = time.time()
    proc, model = load(repo, revision)
    score = fake_score_fn(model)
    paths = [(p, 0) for p in sorted((DATA / "real").glob("*"))] + [(p, 1) for p in sorted((DATA / "fake").glob("*"))]

    full_y, full_s, crop_y, crop_s = [], [], [], []
    batch_imgs, batch_y = [], []

    def flush_full():
        if batch_imgs:
            full_s.extend(score(proc, batch_imgs))
            full_y.extend(batch_y)
            batch_imgs.clear()
            batch_y.clear()

    for path, y in paths:
        img = Image.open(path).convert("RGB")
        batch_imgs.append(img)
        batch_y.append(y)
        if len(batch_imgs) == 16:
            flush_full()
        boxes = detect_faces(img)
        if boxes:
            crop_s.extend(score(proc, [crop_face(img, boxes[0])]))
            crop_y.append(y)
    flush_full()

    def auc(y, s):
        return float(roc_auc_score(y, s)) if len(set(y)) == 2 else None

    return {
        "repo": repo,
        "revision": revision,
        "n_full": len(full_y),
        "roc_auc_full_image": auc(full_y, full_s),
        "n_face_crop": len(crop_y),
        "roc_auc_face_crop": auc(crop_y, crop_s),
        "mean_score_real_full": float(np.mean([s for s, y in zip(full_s, full_y) if y == 0])),
        "mean_score_fake_full": float(np.mean([s for s, y in zip(full_s, full_y) if y == 1])),
        "seconds": round(time.time() - t0, 1),
    }


def main() -> None:
    results = []
    for repo, rev, lic in MODELS:
        print(f"== {repo}", flush=True)
        try:
            r = run_model(repo, rev)
            r["license"] = lic
        except Exception as exc:  # одна модель не должна ронять сравнение
            r = {"repo": repo, "error": f"{type(exc).__name__}: {str(exc)[:300]}", "license": lic}
        print(json.dumps(r, ensure_ascii=False, indent=1), flush=True)
        results.append(r)

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = {"evaluated_at": datetime.now(timezone.utc).isoformat(), "dataset": "DeepFakeFace seed 7 (200 real + 200 fake)",
           "results": results}
    (REPORTS / "model_comparison.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["# Сравнение детекторов дипфейков", "", f"Выборка: {out['dataset']}. Дата: {out['evaluated_at']}.", "",
             "| модель | лицензия | ROC-AUC (полное фото) | ROC-AUC (лицо) | n лицо | среднее real / fake |",
             "|---|---|---|---|---|---|"]
    for r in results:
        if "error" in r:
            lines.append(f"| {r['repo']} | {r['license']} | ошибка: {r['error'][:80]} | | | |")
        else:
            lines.append(f"| {r['repo']} | {r['license']} | {r['roc_auc_full_image']:.3f} | "
                         f"{(r['roc_auc_face_crop'] or 0):.3f} | {r['n_face_crop']} | "
                         f"{r['mean_score_real_full']:.2f} / {r['mean_score_fake_full']:.2f} |")
    (REPORTS / "model_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
