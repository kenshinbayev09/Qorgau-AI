"""Evaluate the backend deepfake pipeline on a labelled image folder (course week 9).

Expected layout:  <data-dir>/real/*.jpg|png   <data-dir>/fake/*.jpg|png
The SAME code path as the API is used (face detection -> crop -> ViT -> score),
so "no face found" cases are counted separately as abstentions.

Usage:
  python ml/deepfake/evaluate.py --data-dir ml/data/deepfake_eval [--threshold 0.5]
Outputs ml/reports/deepfake_eval.json and .md
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score  # noqa: E402

from app.deepfake.analysis import Limits, analyse  # noqa: E402
from app.deepfake.detector import DeepfakeDetector  # noqa: E402
from app.deepfake.media import MediaError  # noqa: E402

DEFAULT_MODEL = ROOT / "ml" / "deepfake" / "weights" / "community-forensics-vit"
REPORTS = ROOT / "ml" / "reports"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL)
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--no-face-crop", action="store_true",
                    help="ablation: score whole images instead of the API face-crop pipeline")
    args = ap.parse_args()

    det = DeepfakeDetector(args.model_dir, threads=4)
    det.load()
    if det.model is None:
        sys.exit(f"Model not available: {det.status} {det.error}. Run ml/deepfake/download_weights.py")

    rows = []
    t0 = time.time()
    for label_name, y in (("real", 0), ("fake", 1)):
        files = sorted(p for p in (args.data_dir / label_name).glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
        for p in files:
            if args.no_face_crop:
                from PIL import Image

                with Image.open(p) as im:
                    s = det.predict([im.convert("RGB")])[0]
                rows.append({"file": p.name, "y": y, "score": s, "status": "done", "reason": None})
                continue
            try:
                r = analyse(str(p), "image", det, Limits())
                rows.append({"file": p.name, "y": y, "score": r["score"], "status": r["status"], "reason": r["reason"]})
            except MediaError as exc:
                rows.append({"file": p.name, "y": y, "score": None, "status": "error", "reason": exc.code})
    scored = [r for r in rows if r["score"] is not None]
    if not scored or len({r["y"] for r in scored}) < 2:
        sys.exit("Not enough scored images of both classes")
    y_true = [r["y"] for r in scored]
    y_score = [r["score"] for r in scored]
    y_pred = [int(s >= args.threshold) for s in y_score]
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    abst = {lbl: sum(1 for r in rows if r["y"] == y and r["score"] is None) for lbl, y in (("real", 0), ("fake", 1))}
    report = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": str(args.data_dir.relative_to(ROOT) if args.data_dir.is_relative_to(ROOT) else args.data_dir),
        "manifest": json.loads((args.data_dir / "manifest.json").read_text()) if (args.data_dir / "manifest.json").exists() else None,
        "model_dir": args.model_dir.name,
        "mode": "full_image_ablation" if args.no_face_crop else "api_pipeline_face_crop",
        "threshold": args.threshold,
        "n_images": len(rows),
        "n_scored": len(scored),
        "abstained_no_face": abst,
        "precision_fake": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall_fake": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1_fake": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_score)),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "seconds": round(time.time() - t0, 1),
    }
    if report["manifest"]:
        report["manifest"] = {k: v for k, v in report["manifest"].items() if k not in ("real", "fake")}
    REPORTS.mkdir(parents=True, exist_ok=True)
    suffix = "_full_image" if args.no_face_crop else ""
    (REPORTS / f"deepfake_eval{suffix}.json").write_text(json.dumps(report | {"rows": rows}, indent=1))
    md = [f"# Deepfake detector evaluation", "", f"Generated {report['evaluated_at']} by `ml/deepfake/evaluate.py`.", "",
          "| metric | value |", "|---|---|"]
    for k in ("mode", "n_images", "n_scored", "abstained_no_face", "threshold", "precision_fake", "recall_fake", "f1_fake",
              "roc_auc", "confusion_matrix", "seconds"):
        v = report[k]
        md.append(f"| {k} | {v:.4f} |" if isinstance(v, float) and k != "threshold" else f"| {k} | {v} |")
    (REPORTS / f"deepfake_eval{suffix}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
