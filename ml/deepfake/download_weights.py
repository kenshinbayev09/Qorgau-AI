"""Скачивает предобученный детектор дипфейков, используемый сервером.

Модель: buildborderless/CommunityForensics-DeepfakeDet-ViT (Hugging Face)
  * архитектура: ViT-Small/16 (384), один выход: вероятность подделки (сигмоида)
  * лицензия: MIT (карточка модели)
  * ревизия зафиксирована ниже, чтобы результаты были воспроизводимы
  * требуется transformers >= 5.4 (см. карточку модели)

Скачиваются только файлы для инференса. Результаты сравнения моделей:
ml/reports/model_comparison.md.

Использование:  python ml/deepfake/download_weights.py [--dest DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parents[2]
REPO_ID = "buildborderless/CommunityForensics-DeepfakeDet-ViT"
REVISION = "ac6ee457bea904a373065754107451793b56db00"
FILES = ["config.json", "preprocessor_config.json", "model.safetensors", "README.md", "LICENSE"]
DEFAULT_DEST = ROOT / "ml" / "deepfake" / "weights" / "community-forensics-vit"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    args = ap.parse_args()
    args.dest.mkdir(parents=True, exist_ok=True)
    manifest = {"repo_id": REPO_ID, "revision": REVISION, "license": "mit", "files": {}}
    for name in FILES:
        path = Path(hf_hub_download(REPO_ID, name, revision=REVISION, local_dir=args.dest))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest["files"][name] = {"sha256": digest, "bytes": path.stat().st_size}
        print(f"{name}: {path.stat().st_size / 1e6:.1f} MB sha256={digest[:16]}…")
    (args.dest / "qorgau_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Сохранено в {args.dest}")


if __name__ == "__main__":
    main()
