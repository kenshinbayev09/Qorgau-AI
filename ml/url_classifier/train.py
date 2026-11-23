"""Train and evaluate the phishing URL classifier (course week 8).

Usage (from repository root):
    python ml/url_classifier/download_data.py      # fetch datasets (once)
    python ml/url_classifier/train.py              # train + evaluate + export

Pipeline
  1. Load PhiUSIIL (UCI #967) and Hannousse & Yahiouche (2021) URL datasets.
  2. Canonicalise URLs with the backend parser, drop unparsable rows,
     drop exact duplicates and URLs with conflicting labels.
  3. Split train/validation/test by *registered domain* (GroupShuffleSplit),
     so no registered domain appears in two splits.
  4. Extract lexical features (backend/app/url_analysis/features.py).
  5. Compare: majority baseline, rule baseline, Logistic Regression,
     Random Forest. Hyper-parameters are chosen on validation only.
  6. Report precision / recall / F1 / ROC-AUC / confusion matrix on test,
     per source, plus a cross-dataset experiment.
  7. Export the selected model to backend/models/url_classifier.joblib.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.url_analysis.brand import analyse_brand  # noqa: E402
from app.url_analysis.features import FEATURE_NAMES, extract_features  # noqa: E402
from app.url_analysis.heuristics import lexical_signals, rule_score  # noqa: E402
from app.url_analysis.normalize import UrlValidationError, parse_url  # noqa: E402

RAW = ROOT / "ml" / "data" / "raw"
CACHE = ROOT / "ml" / "data" / "processed"
REPORTS = ROOT / "ml" / "reports"
MODEL_OUT = ROOT / "backend" / "models" / "url_classifier.joblib"
SEED = 42


def load_raw() -> pd.DataFrame:
    phi = pd.read_csv(RAW / "PhiUSIIL_Phishing_URL_Dataset.csv", usecols=["URL", "label"], encoding="utf-8-sig")
    # PhiUSIIL: label 1 = legitimate, 0 = phishing  ->  y = 1 means phishing
    phi = pd.DataFrame({"url": phi["URL"].astype(str), "y": (1 - phi["label"]).astype(int), "source": "phiusiil"})
    frames = [phi]
    for part in ("train", "test"):
        h = pd.read_parquet(RAW / "hannousse" / f"{part}.parquet", columns=["url", "status"])
        frames.append(pd.DataFrame({"url": h["url"].astype(str), "y": (h["status"] == "phishing").astype(int),
                                    "source": "hannousse"}))
    return pd.concat(frames, ignore_index=True)


def featurise(df: pd.DataFrame) -> pd.DataFrame:
    rows, keep = [], []
    t0 = time.time()
    for i, url in enumerate(df["url"].tolist()):
        try:
            p = parse_url(url)
        except UrlValidationError:
            continue
        brand = analyse_brand(p)
        f = extract_features(p, brand)
        f["rule_score"] = rule_score(lexical_signals(p, brand))
        f["canonical"] = p.canonical
        f["group"] = p.registered_domain
        rows.append(f)
        keep.append(i)
        if i and i % 50000 == 0:
            print(f"  featurised {i:,} rows in {time.time() - t0:.0f}s", flush=True)
    feats = pd.DataFrame(rows)
    out = pd.concat([df.iloc[keep].reset_index(drop=True), feats], axis=1)
    return out


def metrics(y_true, y_pred, y_score=None) -> dict:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    m = {
        "n": int(len(y_true)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }
    if y_score is not None and len(set(y_true)) == 2:
        m["roc_auc"] = float(roc_auc_score(y_true, y_score))
    return m


def source_weights(df: pd.DataFrame) -> np.ndarray:
    """Give each data source equal total weight (Hannousse is ~20x smaller)."""
    counts = df["source"].value_counts()
    w = df["source"].map(lambda s: len(df) / (len(counts) * counts[s])).to_numpy()
    return w


def grouped_split(df: pd.DataFrame):
    gss = GroupShuffleSplit(n_splits=1, test_size=0.15, random_state=SEED)
    trval_idx, test_idx = next(gss.split(df, groups=df["group"]))
    trval = df.iloc[trval_idx]
    gss2 = GroupShuffleSplit(n_splits=1, test_size=0.15 / 0.85, random_state=SEED)
    tr_idx, val_idx = next(gss2.split(trval, groups=trval["group"]))
    return trval.iloc[tr_idx].reset_index(drop=True), trval.iloc[val_idx].reset_index(drop=True), \
        df.iloc[test_idx].reset_index(drop=True)


def fit_candidates(train: pd.DataFrame, val: pd.DataFrame, weighted: bool):
    X_tr, y_tr = train[FEATURE_NAMES].to_numpy(), train["y"].to_numpy()
    X_val, y_val = val[FEATURE_NAMES].to_numpy(), val["y"].to_numpy()
    sw = source_weights(train) if weighted else None
    results = {}

    # Baseline 1: majority class
    dummy = DummyClassifier(strategy="most_frequent").fit(X_tr, y_tr)
    results["baseline_majority"] = {"model": dummy, "params": {}, "val": metrics(y_val, dummy.predict(X_val))}

    # Baseline 2: hand-written rules (threshold tuned on validation)
    best = None
    for thr in np.arange(0.1, 0.95, 0.05):
        m = metrics(y_val, (val["rule_score"].to_numpy() >= thr).astype(int), val["rule_score"].to_numpy())
        if best is None or m["f1"] > best[1]["f1"]:
            best = (float(round(thr, 2)), m)
    results["baseline_rules"] = {"model": None, "params": {"threshold": best[0]}, "val": best[1]}

    # Logistic Regression
    best = None
    for C in (0.01, 0.1, 1.0, 10.0):
        lr = Pipeline([("scale", StandardScaler()),
                       ("clf", LogisticRegression(C=C, max_iter=3000, class_weight="balanced"))])
        lr.fit(X_tr, y_tr, clf__sample_weight=sw)
        s = lr.predict_proba(X_val)[:, 1]
        m = metrics(y_val, (s >= 0.5).astype(int), s)
        print(f"  LR C={C}: val F1={m['f1']:.4f}", flush=True)
        if best is None or m["f1"] > best[2]["f1"]:
            best = (lr, {"C": C}, m)
    results["logistic_regression"] = {"model": best[0], "params": best[1], "val": best[2]}

    # Random Forest
    best = None
    for leaf in (1, 5):
        for depth in (None, 20):
            rf = RandomForestClassifier(n_estimators=300, min_samples_leaf=leaf, max_depth=depth, n_jobs=-1,
                                        class_weight="balanced_subsample", random_state=SEED)
            rf.fit(X_tr, y_tr, sample_weight=sw)
            s = rf.predict_proba(X_val)[:, 1]
            m = metrics(y_val, (s >= 0.5).astype(int), s)
            print(f"  RF leaf={leaf} depth={depth}: val F1={m['f1']:.4f}", flush=True)
            if best is None or m["f1"] > best[2]["f1"]:
                best = (rf, {"n_estimators": 300, "min_samples_leaf": leaf, "max_depth": depth}, m)
    results["random_forest"] = {"model": best[0], "params": best[1], "val": best[2]}
    return results


def evaluate(results: dict, test: pd.DataFrame) -> None:
    X_te, y_te = test[FEATURE_NAMES].to_numpy(), test["y"].to_numpy()
    for name, r in results.items():
        r["test"] = {}
        for subset_name, mask in [("all", np.ones(len(test), bool))] + \
                [(s, (test["source"] == s).to_numpy()) for s in sorted(test["source"].unique())]:
            if mask.sum() == 0:
                continue
            if name == "baseline_rules":
                s = test["rule_score"].to_numpy()[mask]
                pred = (s >= r["params"]["threshold"]).astype(int)
            elif name == "baseline_majority":
                s, pred = None, r["model"].predict(X_te[mask])
            else:
                s = r["model"].predict_proba(X_te[mask])[:, 1]
                pred = (s >= 0.5).astype(int)
            r["test"][subset_name] = metrics(y_te[mask], pred, s)


def plot_confusion(cm: dict, title: str, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    arr = np.array([[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]])
    fig, ax = plt.subplots(figsize=(4, 3.6))
    ax.imshow(arr, cmap="Blues")
    for (i, j), v in np.ndenumerate(arr):
        ax.text(j, i, f"{v:,}", ha="center", va="center", color="black" if v < arr.max() / 2 else "white")
    ax.set_xticks([0, 1], ["legit", "phishing"])
    ax.set_yticks([0, 1], ["legit", "phishing"])
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title(title, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-source-weighting", action="store_true")
    ap.add_argument("--refeaturise", action="store_true")
    args = ap.parse_args()
    weighted = not args.no_source_weighting
    REPORTS.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE / "features.parquet"

    if cache_file.exists() and not args.refeaturise:
        df = pd.read_parquet(cache_file)
        n_raw = int(json.loads((CACHE / "prep_stats.json").read_text())["n_raw"])
        prep = json.loads((CACHE / "prep_stats.json").read_text())
    else:
        raw = load_raw()
        n_raw = len(raw)
        print(f"Loaded {n_raw:,} raw rows; featurising...", flush=True)
        df = featurise(raw)
        n_parsed = len(df)
        # conflicting labels for the same canonical URL -> drop all copies
        conflict = df.groupby("canonical")["y"].nunique()
        conflict_urls = set(conflict[conflict > 1].index)
        df = df[~df["canonical"].isin(conflict_urls)]
        n_after_conflict = len(df)
        df = df.drop_duplicates(subset="canonical").reset_index(drop=True)
        prep = {
            "n_raw": n_raw,
            "n_unparsable_dropped": n_raw - n_parsed,
            "n_conflicting_label_urls_dropped": len(conflict_urls),
            "n_rows_with_conflicting_labels_dropped": n_parsed - n_after_conflict,
            "n_duplicates_dropped": n_after_conflict - len(df),
            "n_final": len(df),
            "per_source": df.groupby(["source", "y"]).size().rename("n").reset_index().to_dict("records"),
        }
        df.to_parquet(cache_file)
        (CACHE / "prep_stats.json").write_text(json.dumps(prep, indent=2))
    print("Prep:", json.dumps({k: v for k, v in prep.items() if k != "per_source"}), flush=True)

    train, val, test = grouped_split(df)
    overlap = {
        "train_val": len(set(train["group"]) & set(val["group"])),
        "train_test": len(set(train["group"]) & set(test["group"])),
        "val_test": len(set(val["group"]) & set(test["group"])),
    }
    assert sum(overlap.values()) == 0, overlap
    split_info = {name: {"n": len(d), "phishing": int(d["y"].sum()), "legit": int((1 - d["y"]).sum()),
                         "domains": int(d["group"].nunique()),
                         "by_source": d["source"].value_counts().to_dict()}
                  for name, d in (("train", train), ("validation", val), ("test", test))}
    print("Splits:", json.dumps(split_info), "domain overlap:", overlap, flush=True)

    print("Fitting candidates on combined data...", flush=True)
    results = fit_candidates(train, val, weighted)
    evaluate(results, test)

    selectable = ["logistic_regression", "random_forest"]
    selected = max(selectable, key=lambda k: results[k]["val"]["f1"])
    print("Selected by validation F1:", selected, flush=True)

    # Cross-dataset experiment: train on PhiUSIIL only, test on Hannousse test split.
    print("Cross-dataset experiment (train PhiUSIIL only)...", flush=True)
    tr_phi, val_phi = train[train["source"] == "phiusiil"], val[val["source"] == "phiusiil"]
    cross = fit_candidates(tr_phi, val_phi, weighted=False)
    test_h = test[test["source"] == "hannousse"]
    evaluate(cross, test_h)
    cross_summary = {k: {"params": v["params"], "test_hannousse": v["test"].get("all")} for k, v in cross.items()}

    # Feature importances (RF) / coefficients (LR)
    rf = results["random_forest"]["model"]
    importances = sorted(zip(FEATURE_NAMES, rf.feature_importances_.tolist()), key=lambda x: -x[1])
    lr_coef = sorted(zip(FEATURE_NAMES, results["logistic_regression"]["model"].named_steps["clf"].coef_[0].tolist()),
                     key=lambda x: -abs(x[1]))

    for name in ("baseline_rules", "logistic_regression", "random_forest"):
        plot_confusion(results[name]["test"]["all"]["confusion_matrix"], f"{name} - test (combined)",
                       REPORTS / f"cm_{name}.png")

    data_hash = hashlib.sha256(pd.util.hash_pandas_object(df["canonical"], index=False).values.tobytes()).hexdigest()[:16]
    version = f"url-{selected[:2]}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{data_hash[:8]}"
    report = {
        "version": version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "selected_model": selected,
        "source_weighting": weighted,
        "feature_names": FEATURE_NAMES,
        "data_preparation": prep,
        "splits": split_info,
        "domain_overlap": overlap,
        "models": {k: {"params": v["params"], "validation": v["val"], "test": v["test"]} for k, v in results.items()},
        "cross_dataset_phiusiil_to_hannousse": cross_summary,
        "rf_feature_importance_top15": importances[:15],
        "lr_coefficients_top15": lr_coef[:15],
    }
    (REPORTS / "url_classifier_metrics.json").write_text(json.dumps(report, indent=2, default=str))

    MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "model": results[selected]["model"],
        "feature_names": FEATURE_NAMES,
        "version": version,
        "model_type": selected,
        "threshold": 0.5,
        "test_metrics": results[selected]["test"]["all"],
        "trained_at": report["trained_at"],
    }, MODEL_OUT, compress=3)
    print(f"Saved model -> {MODEL_OUT} ({MODEL_OUT.stat().st_size / 1e6:.1f} MB), version {version}")
    write_markdown(report)


def write_markdown(r: dict) -> None:
    lines = [f"# URL classifier evaluation ({r['version']})", "",
             f"Generated by `ml/url_classifier/train.py` at {r['trained_at']}.", "",
             "## Data", "", "```json", json.dumps(r["data_preparation"], indent=2), "```", "",
             "## Splits (grouped by registered domain)", "", "| split | n | phishing | legit | domains |",
             "|---|---|---|---|---|"]
    for k, v in r["splits"].items():
        lines.append(f"| {k} | {v['n']:,} | {v['phishing']:,} | {v['legit']:,} | {v['domains']:,} |")
    lines += ["", f"Registered-domain overlap between splits: `{r['domain_overlap']}`", "",
              "## Test metrics (threshold 0.5; rules baseline uses validation-tuned threshold)", "",
              "| model | subset | n | precision | recall | F1 | ROC-AUC | TN | FP | FN | TP |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, m in r["models"].items():
        for subset, t in m["test"].items():
            cm = t["confusion_matrix"]
            auc = f"{t['roc_auc']:.4f}" if "roc_auc" in t else "-"
            lines.append(f"| {name} | {subset} | {t['n']:,} | {t['precision']:.4f} | {t['recall']:.4f} | "
                         f"{t['f1']:.4f} | {auc} | {cm['tn']:,} | {cm['fp']:,} | {cm['fn']:,} | {cm['tp']:,} |")
    lines += ["", f"Selected model (by validation F1): **{r['selected_model']}**", "",
              "## Cross-dataset: trained on PhiUSIIL only, tested on Hannousse test domains", "",
              "| model | n | precision | recall | F1 | ROC-AUC |", "|---|---|---|---|---|---|"]
    for name, v in r["cross_dataset_phiusiil_to_hannousse"].items():
        t = v["test_hannousse"]
        auc = f"{t['roc_auc']:.4f}" if "roc_auc" in t else "-"
        lines.append(f"| {name} | {t['n']:,} | {t['precision']:.4f} | {t['recall']:.4f} | {t['f1']:.4f} | {auc} |")
    lines += ["", "## Random Forest feature importance (top 15)", ""]
    lines += [f"- `{n}`: {v:.4f}" for n, v in r["rf_feature_importance_top15"]]
    lines += ["", "## Logistic Regression coefficients (standardised, top 15 by |coef|)", ""]
    lines += [f"- `{n}`: {v:+.3f}" for n, v in r["lr_coefficients_top15"]]
    (REPORTS / "url_classifier_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
