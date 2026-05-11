"""
Step 3 / Random Forest Training
================================
Trains a Random Forest classifier on the processed dataset using:
    - Time-based CV (NOT random split — would leak temporal autocorrelation)
    - class_weight='balanced' (rain is the minority class)
    - Hold-out test = last 20 % of the time-ordered dataset

Outputs:
    models/rf_model.pkl              — fitted estimator
    models/feature_columns.json      — exact feature order used at train time
    models/training_report.json      — metrics + feature importance + meta

Run:  python scripts/3_train_model.py
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.model_selection import TimeSeriesSplit

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR  = ROOT / "data"
MODEL_DIR = ROOT / "models"
MODEL_DIR.mkdir(exist_ok=True)

# Features fed to the model (X). Order matters — saved alongside the model.
FEATURE_COLUMNS: list[str] = [
    "elevation_m",
    "temperature_c",
    "humidity_pct",
    "wind_speed_kmh",
    "wind_direction_deg",   # kept for interpretability comparison
    "wind_u", "wind_v",     # mathematically correct circular decomposition
    "pressure_hpa",
    "pressure_change_3h",
    "dew_point_c",
    "dew_point_depression",
    "cloud_cover_pct",
    "cape_jkg",
    "precipitation_lag_1h",
    "hour_sin", "hour_cos",
    "month_sin", "month_cos",
]
TARGET = "is_rain_event"


def load_dataset() -> pd.DataFrame:
    p = DATA_DIR / "processed.csv"
    if not p.exists():
        raise SystemExit("ERROR: data/processed.csv not found. "
                         "Run scripts/2_preprocess.py first.")
    df = pd.read_csv(p, parse_dates=["time"])
    df = df.sort_values(["site", "time"]).reset_index(drop=True)
    return df


def time_based_split(df: pd.DataFrame, test_frac: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Last `test_frac` of the time-ordered data per site is held out."""
    train_parts, test_parts = [], []
    for _, g in df.groupby("site", sort=False):
        cut = int(len(g) * (1.0 - test_frac))
        train_parts.append(g.iloc[:cut])
        test_parts.append(g.iloc[cut:])
    return pd.concat(train_parts, ignore_index=True), pd.concat(test_parts, ignore_index=True)


def crossval_score(X: np.ndarray, y: np.ndarray, n_splits: int = 5) -> list[dict]:
    """TimeSeriesSplit gives a fair temporal-CV estimate."""
    tscv = TimeSeriesSplit(n_splits=n_splits)
    fold_metrics: list[dict] = []
    for fold, (tr, va) in enumerate(tscv.split(X), start=1):
        model = RandomForestClassifier(
            n_estimators=200,
            max_depth=15,
            min_samples_leaf=20,
            class_weight="balanced",
            n_jobs=-1,
            random_state=42,
        )
        model.fit(X[tr], y[tr])
        proba = model.predict_proba(X[va])[:, 1]
        pred  = (proba >= 0.5).astype(int)
        p, r, f1, _ = precision_recall_fscore_support(y[va], pred, average="binary", zero_division=0)
        try:
            auc = roc_auc_score(y[va], proba)
        except ValueError:
            auc = float("nan")
        f2 = fbeta_score(y[va], pred, beta=2.0, zero_division=0)
        print(f"  fold {fold}: P={p:.3f}  R={r:.3f}  F1={f1:.3f}  F2={f2:.3f}  AUC={auc:.3f}")
        fold_metrics.append({"fold": fold, "precision": p, "recall": r,
                              "f1": f1, "f2": f2, "auc": auc})
    return fold_metrics


def main() -> int:
    print("Loading processed dataset…")
    df = load_dataset()
    print(f"  rows: {len(df):,}   features: {len(FEATURE_COLUMNS)}")
    print(f"  class balance (Y=1): {df[TARGET].mean():.1%}")

    print("\nTime-based train/test split (last 20% per site held out)…")
    train_df, test_df = time_based_split(df, test_frac=0.20)
    print(f"  train: {len(train_df):,}   test: {len(test_df):,}")

    X_train = train_df[FEATURE_COLUMNS].to_numpy()
    y_train = train_df[TARGET].to_numpy()
    X_test  = test_df[FEATURE_COLUMNS].to_numpy()
    y_test  = test_df[TARGET].to_numpy()

    print("\nTime-series cross-validation on training fold (5 splits)…")
    fold_metrics = crossval_score(X_train, y_train, n_splits=5)

    print("\nFitting final model on full training set…")
    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=20,
        min_samples_leaf=10,
        class_weight="balanced",
        n_jobs=-1,
        random_state=42,
    )
    model.fit(X_train, y_train)

    print("\nEvaluating on held-out test set…")
    proba = model.predict_proba(X_test)[:, 1]
    pred  = (proba >= 0.5).astype(int)
    print(classification_report(y_test, pred, target_names=["NoRain", "Rain"], digits=3))
    cm = confusion_matrix(y_test, pred)
    print("Confusion matrix:")
    print(f"  [[TN={cm[0,0]:>6}  FP={cm[0,1]:>6}]")
    print(f"   [FN={cm[1,0]:>6}  TP={cm[1,1]:>6}]]")
    auc_test = roc_auc_score(y_test, proba)
    f2_test  = fbeta_score(y_test, pred, beta=2.0, zero_division=0)
    print(f"AUC = {auc_test:.3f}    F2 = {f2_test:.3f}")

    print("\nFeature importances:")
    fi = sorted(zip(FEATURE_COLUMNS, model.feature_importances_), key=lambda x: -x[1])
    for name, imp in fi:
        bar = "█" * int(imp * 200)
        print(f"  {name:<24} {imp:.4f} {bar}")

    print("\nSaving artefacts…")
    joblib.dump(model, MODEL_DIR / "rf_model.pkl")
    with open(MODEL_DIR / "feature_columns.json", "w") as f:
        json.dump(FEATURE_COLUMNS, f, indent=2)
    with open(MODEL_DIR / "training_report.json", "w") as f:
        json.dump({
            "n_train":        int(len(train_df)),
            "n_test":         int(len(test_df)),
            "class_balance":  float(df[TARGET].mean()),
            "cv_fold_metrics": fold_metrics,
            "test_metrics": {
                "f1":  float(f1_score(y_test, pred, zero_division=0)),
                "f2":  float(f2_test),
                "auc": float(auc_test),
                "confusion_matrix": cm.tolist(),
            },
            "feature_importance": {name: float(imp) for name, imp in fi},
        }, f, indent=2)

    print(f"  → {MODEL_DIR/'rf_model.pkl'}")
    print(f"  → {MODEL_DIR/'feature_columns.json'}")
    print(f"  → {MODEL_DIR/'training_report.json'}")
    print("\nNext step:  uvicorn backend.main:app --reload --port 8000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
