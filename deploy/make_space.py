"""Собирает папку, которую нужно загрузить в Hugging Face Space (SDK = Docker).

Usage (из корня проекта):
    python deploy/make_space.py --dest ../qorgau-space

Копируется только то, что нужно серверу: код backend/app, requirements,
файл модели URL, скрипт загрузки весов детектора, Dockerfile и README для Space.
Тесты, мобильное приложение, датасеты, отчёты и .venv не копируются.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPACE_DIR = ROOT / "deploy" / "space"


def copy_file(src: Path, dst: Path) -> None:
    if not src.exists():
        raise SystemExit(f"Не найден файл: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"  {src.relative_to(ROOT)} -> {dst}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", type=Path, required=True, help="папка Space-репозитория (будет создана)")
    args = ap.parse_args()
    dest: Path = args.dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)

    print(f"Сборка Space в {dest}")
    copy_file(SPACE_DIR / "Dockerfile", dest / "Dockerfile")
    copy_file(SPACE_DIR / "README.md", dest / "README.md")

    # Код сервера (без тестов и кэшей)
    app_src = ROOT / "backend" / "app"
    app_dst = dest / "backend" / "app"
    if app_dst.exists():
        shutil.rmtree(app_dst)
    shutil.copytree(app_src, app_dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    print(f"  backend/app -> {app_dst}")

    copy_file(ROOT / "backend" / "requirements.txt", dest / "backend" / "requirements.txt")
    copy_file(ROOT / "backend" / "models" / "url_classifier.joblib",
              dest / "backend" / "models" / "url_classifier.joblib")
    copy_file(ROOT / "ml" / "deepfake" / "download_weights.py", dest / "ml" / "deepfake" / "download_weights.py")

    (dest / ".dockerignore").write_text("**/__pycache__\n**/*.pyc\n.env\n", encoding="utf-8")
    print("Готово. Дальше: загрузите содержимое папки в Space (см. deploy/DEPLOY.md).")


if __name__ == "__main__":
    main()
