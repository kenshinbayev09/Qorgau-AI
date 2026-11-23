import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.config import REPO_DIR  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
MODEL_DIR = REPO_DIR / "ml" / "deepfake" / "weights" / "community-forensics-vit"
URL_MODEL = BACKEND / "models" / "url_classifier.joblib"

requires_deepfake_weights = pytest.mark.skipif(
    not (MODEL_DIR / "model.safetensors").exists(), reason="deepfake weights not downloaded")
requires_url_model = pytest.mark.skipif(not URL_MODEL.exists(), reason="URL model not trained")
