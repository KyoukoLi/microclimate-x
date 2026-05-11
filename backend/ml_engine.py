"""
ML Predictor wrapper.

The trained Random Forest is loaded ONCE at FastAPI startup (lifespan)
and held in memory — never reload inside a request handler.

When the model artefact is missing we fall back to a calibrated heuristic
so that the FastAPI demo still runs end-to-end before `scripts/3_train_model.py`
has been executed.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import joblib

from . import config


class MLEngine:
    """Lightweight wrapper around the joblibbed RandomForestClassifier."""

    def __init__(self) -> None:
        self.model: Any | None = None
        self.feature_columns: list[str] = []
        self.loaded_from: str | None = None

    def load(self) -> None:
        model_path    = config.MODEL_DIR / "rf_model.pkl"
        features_path = config.MODEL_DIR / "feature_columns.json"
        if model_path.exists() and features_path.exists():
            self.model = joblib.load(model_path)
            self.feature_columns = json.loads(features_path.read_text())
            self.loaded_from = str(model_path)
        else:
            self.model = None
            self.loaded_from = None

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    def predict_rain_probability(self, feats: dict[str, float]) -> float:
        """Return P(rain in next hour) ∈ [0, 1]."""
        if self.is_loaded:
            X = [[feats.get(col, 0.0) for col in self.feature_columns]]
            return float(self.model.predict_proba(X)[0, 1])
        return self._fallback_heuristic(feats)

    @staticmethod
    def _fallback_heuristic(f: dict[str, float]) -> float:
        """Smooth, physically-motivated proxy used when no trained model
        exists yet. Lets the FastAPI demo work end-to-end before training."""
        humidity = f.get("humidity_pct", 60.0)
        dew_dep  = f.get("dew_point_depression", 5.0)
        cloud    = f.get("cloud_cover_pct", 50.0)
        cape     = f.get("cape_jkg", 0.0)
        prev     = f.get("precipitation_lag_1h", 0.0)

        z = (
            0.05 * (humidity - 70.0)
            - 0.20 * dew_dep
            + 0.02 * (cloud - 50.0)
            + 0.0015 * cape
            + 1.50 * (1.0 if prev > 0.1 else 0.0)
        )
        return 1.0 / (1.0 + math.exp(-z))
