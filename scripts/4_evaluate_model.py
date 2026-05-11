"""
Step 4 / Model Evaluation
==========================
Produces *publication-quality* figures that can be pasted directly into
the thesis (Chapter 5 — Results / Discussion). Run AFTER 3_train_model.py.

Inputs
------
    models/rf_model.pkl
    models/feature_columns.json
    data/processed.csv

Outputs
-------
    figures/01_roc_curve.png            ROC + AUC
    figures/02_pr_curve.png             Precision-Recall + AP
    figures/03_calibration_curve.png    Reliability diagram + Brier score
    figures/04_threshold_sweep.png      F1 / F2 / Precision / Recall vs threshold
    figures/05_feature_importance.png   Top-20 features (horizontal bar)
    figures/06_confusion_matrix.png     Confusion matrix at optimal F2 threshold
    figures/threshold_sweep.csv         Same data as 04 in machine-readable form
    figures/evaluation_summary.json     One-shot metrics blob for the thesis

Run:  python scripts/4_evaluate_model.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    auc,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_curve,
)

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "models"
DATA_DIR  = ROOT / "data"
FIG_DIR   = ROOT / "figures"
FIG_DIR.mkdir(exist_ok=True)

# ── Matplotlib defaults — keep figures consistent across panels ──────────
plt.rcParams.update({
    "figure.figsize":  (7.0, 4.5),
    "figure.dpi":      120,
    "savefig.dpi":     200,
    "savefig.bbox":    "tight",
    "font.size":       11,
    "axes.titlesize":  13,
    "axes.labelsize":  11,
    "legend.fontsize": 10,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "grid.alpha":        0.25,
    "axes.axisbelow":    True,
})


# ── Load artefacts ───────────────────────────────────────────────────────

def _load() -> tuple:
    model_path = MODEL_DIR / "rf_model.pkl"
    feats_path = MODEL_DIR / "feature_columns.json"
    data_path  = DATA_DIR  / "processed.csv"

    for p in (model_path, feats_path, data_path):
        if not p.exists():
            raise FileNotFoundError(
                f"Missing artefact: {p}. Run scripts/3_train_model.py first."
            )

    model      = joblib.load(model_path)
    feat_cols  = json.loads(feats_path.read_text())
    df         = pd.read_csv(data_path)
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").reset_index(drop=True)

    # Use the last 20% as test (same split as training).
    cut = int(len(df) * 0.80)
    test = df.iloc[cut:].reset_index(drop=True)

    X = test[feat_cols].values
    y = test["is_rain_event"].astype(int).values
    proba = model.predict_proba(X)[:, 1]
    return model, feat_cols, X, y, proba, test


# ── Figure builders ──────────────────────────────────────────────────────

def plot_roc(y, proba) -> dict:
    fpr, tpr, _ = roc_curve(y, proba)
    auc_v = auc(fpr, tpr)

    fig, ax = plt.subplots()
    ax.plot(fpr, tpr, color="#0ea5e9", linewidth=2.0, label=f"RF (AUC = {auc_v:.3f})")
    ax.plot([0, 1], [0, 1], "--", color="#9ca3af", linewidth=1.0, label="Random baseline")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Curve — rain-event classifier")
    ax.legend(loc="lower right")
    ax.grid(True)
    fig.savefig(FIG_DIR / "01_roc_curve.png")
    plt.close(fig)
    return {"auc": float(auc_v)}


def plot_pr(y, proba) -> dict:
    pr, rc, _ = precision_recall_curve(y, proba)
    ap = average_precision_score(y, proba)
    base_rate = float(y.mean())

    fig, ax = plt.subplots()
    ax.plot(rc, pr, color="#10b981", linewidth=2.0, label=f"RF (AP = {ap:.3f})")
    ax.hlines(base_rate, 0, 1, colors="#9ca3af", linestyles="--",
              label=f"Base rate = {base_rate:.3f}")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Precision–Recall Curve")
    ax.legend(loc="lower left")
    ax.grid(True)
    fig.savefig(FIG_DIR / "02_pr_curve.png")
    plt.close(fig)
    return {"average_precision": float(ap), "base_rate": base_rate}


def plot_calibration(y, proba) -> dict:
    frac_pos, mean_pred = calibration_curve(y, proba, n_bins=10, strategy="quantile")
    brier = brier_score_loss(y, proba)

    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1], "--", color="#9ca3af", linewidth=1.0,
            label="Perfectly calibrated")
    ax.plot(mean_pred, frac_pos, marker="o", color="#f59e0b", linewidth=2.0,
            label=f"RF (Brier = {brier:.3f})")
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Fraction of positives (observed)")
    ax.set_title("Reliability Diagram — model calibration")
    ax.legend(loc="upper left")
    ax.grid(True)
    fig.savefig(FIG_DIR / "03_calibration_curve.png")
    plt.close(fig)
    return {"brier_score": float(brier)}


def plot_threshold_sweep(y, proba) -> dict:
    thresholds = np.linspace(0.05, 0.95, 19)
    rows = []
    best_f2 = (-1.0, 0.5)
    for thr in thresholds:
        yp = (proba >= thr).astype(int)
        f1   = f1_score(y, yp, zero_division=0)
        f2   = fbeta_score(y, yp, beta=2.0, zero_division=0)
        prec = precision_score(y, yp, zero_division=0)
        rec  = recall_score(y, yp, zero_division=0)
        rows.append({
            "threshold": thr, "f1": f1, "f2": f2,
            "precision": prec, "recall": rec,
        })
        if f2 > best_f2[0]:
            best_f2 = (f2, thr)

    sweep = pd.DataFrame(rows)
    sweep.to_csv(FIG_DIR / "threshold_sweep.csv", index=False)

    fig, ax = plt.subplots()
    ax.plot(sweep.threshold, sweep.precision, label="Precision", color="#0ea5e9", linewidth=2.0)
    ax.plot(sweep.threshold, sweep.recall,    label="Recall",    color="#10b981", linewidth=2.0)
    ax.plot(sweep.threshold, sweep.f1,        label="F1",        color="#f59e0b", linewidth=1.4, linestyle="--")
    ax.plot(sweep.threshold, sweep.f2,        label="F2",        color="#ef4444", linewidth=2.0)
    ax.axvline(best_f2[1], color="#ef4444", alpha=0.25, linestyle=":")
    ax.set_xlabel("Decision threshold")
    ax.set_ylabel("Score")
    ax.set_title(f"Threshold sweep — best F2 = {best_f2[0]:.3f} @ τ = {best_f2[1]:.2f}")
    ax.legend(loc="lower left", ncols=4)
    ax.grid(True)
    fig.savefig(FIG_DIR / "04_threshold_sweep.png")
    plt.close(fig)
    return {"best_f2": float(best_f2[0]), "best_f2_threshold": float(best_f2[1])}


def plot_feature_importance(model, feat_cols, top_n: int = 20) -> dict:
    imp = pd.Series(model.feature_importances_, index=feat_cols)
    imp = imp.sort_values(ascending=True).tail(top_n)

    fig, ax = plt.subplots(figsize=(7.0, 0.32 * len(imp) + 1.2))
    ax.barh(imp.index, imp.values, color="#6366f1")
    ax.set_xlabel("Importance (mean decrease in impurity)")
    ax.set_title(f"Top {len(imp)} feature importances")
    ax.grid(True, axis="x")
    fig.savefig(FIG_DIR / "05_feature_importance.png")
    plt.close(fig)
    return {"feature_importance": imp.sort_values(ascending=False).to_dict()}


def plot_confusion(y, proba, threshold: float) -> dict:
    yp = (proba >= threshold).astype(int)
    cm = confusion_matrix(y, yp)
    tn, fp, fn, tp = cm.ravel()

    fig, ax = plt.subplots(figsize=(4.5, 4.0))
    im = ax.imshow(cm, cmap="Blues")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                    color="black" if cm[i, j] < cm.max() / 2 else "white",
                    fontsize=13, fontweight="bold")
    ax.set_xticks([0, 1], ["No rain", "Rain"])
    ax.set_yticks([0, 1], ["No rain", "Rain"])
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")
    ax.set_title(f"Confusion matrix @ τ = {threshold:.2f}")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.savefig(FIG_DIR / "06_confusion_matrix.png")
    plt.close(fig)
    return {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"[eval] loading artefacts from {MODEL_DIR}")
    model, feat_cols, _, y, proba, _test = _load()
    print(f"[eval] test set: {len(y)} samples  ({int(y.sum())} positives, "
          f"{(y.mean() * 100):.1f}% rain-event rate)")

    summary = {
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "n_test":         len(y),
        "n_positives":    int(y.sum()),
        "positive_rate":  float(y.mean()),
        "n_features":     len(feat_cols),
    }

    summary["roc"]        = plot_roc(y, proba)
    summary["pr"]         = plot_pr(y, proba)
    summary["calibration"] = plot_calibration(y, proba)
    sweep = plot_threshold_sweep(y, proba)
    summary["threshold_sweep"] = sweep
    summary["confusion"]  = plot_confusion(y, proba, sweep["best_f2_threshold"])
    top_importances = plot_feature_importance(model, feat_cols)
    summary["top_features"] = list(top_importances["feature_importance"].keys())[:10]

    out = FIG_DIR / "evaluation_summary.json"
    out.write_text(json.dumps(summary, indent=2))

    print(f"[eval] all figures written to {FIG_DIR}")
    print(f"[eval] summary JSON: {out}")
    print(f"[eval] best F2 = {sweep['best_f2']:.3f} at τ = {sweep['best_f2_threshold']:.2f}")
    print(f"[eval] ROC AUC = {summary['roc']['auc']:.3f},  "
          f"PR AP = {summary['pr']['average_precision']:.3f},  "
          f"Brier = {summary['calibration']['brier_score']:.3f}")


if __name__ == "__main__":
    main()
