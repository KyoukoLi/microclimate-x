"""
ML Predictor wrapper.

The trained Random Forest is loaded ONCE at FastAPI startup (lifespan)
and held in memory — never reload inside a request handler.

When the model artefact is missing we fall back to a physically-motivated
heuristic so the API still runs end-to-end before `scripts/3_train_model.py`
has been executed. The heuristic deliberately uses the same feature names
as the trained model so swapping between them is transparent to callers.
"""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

import joblib

from . import config

log = logging.getLogger("microclimate-x.ml")


class MLEngine:
    """Thin, defensive wrapper around the joblibbed RandomForestClassifier.

    Invariant: ``predict_rain_probability`` ALWAYS returns a float in [0, 1].
    Any internal failure logs and falls through to the heuristic.
    """

    def __init__(self) -> None:
        self.model: Any | None = None
        self.feature_columns: list[str] = []
        self.loaded_from: str | None = None
        self.training_report: dict[str, Any] | None = None

    # ── Load --------------------------------------------------------
    def load(self) -> None:
        model_path    = config.MODEL_DIR / "rf_model.pkl"
        features_path = config.MODEL_DIR / "feature_columns.json"
        report_path   = config.MODEL_DIR / "training_report.json"

        if not (model_path.exists() and features_path.exists()):
            self.model = None
            self.loaded_from = None
            return

        try:
            self.model = joblib.load(model_path)
            self.feature_columns = json.loads(features_path.read_text())
            self.loaded_from = str(model_path)
            if report_path.exists():
                self.training_report = json.loads(report_path.read_text())
            log.info(
                "loaded RF model with %d features (%s)",
                len(self.feature_columns), Path(model_path).name,
            )
        except Exception as exc:   # pragma: no cover — defensive
            log.exception("Failed to load trained model: %s", exc)
            self.model = None
            self.loaded_from = None

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    # ── Predict -----------------------------------------------------
    def predict_rain_probability(self, feats: dict[str, float]) -> float:
        """Return P(rain in next hour) ∈ [0, 1]."""
        if self.is_loaded:
            try:
                X = [[self._safe_feat(feats, col) for col in self.feature_columns]]
                p = float(self.model.predict_proba(X)[0, 1])
                return min(1.0, max(0.0, p))
            except Exception as exc:                          # pragma: no cover
                log.exception("RF inference failed (%s) — falling back to heuristic.", exc)
        return self._fallback_heuristic(feats)

    # ── Helpers -----------------------------------------------------
    @staticmethod
    def _safe_feat(feats: dict[str, float], col: str) -> float:
        v = feats.get(col, 0.0)
        if v is None:
            return 0.0
        try:
            f = float(v)
        except (TypeError, ValueError):
            return 0.0
        if math.isnan(f) or math.isinf(f):
            return 0.0
        return f

    @staticmethod
    def _fallback_heuristic(f: dict[str, float]) -> float:
        """Smooth, physically-motivated proxy used when no trained model
        exists yet. Uses the same feature inputs as the trained model so the
        downstream rule engine sees no behaviour change."""
        humidity = MLEngine._safe_get(f, "humidity_pct", 60.0)
        dew_dep  = MLEngine._safe_get(f, "dew_point_depression", 5.0)
        cloud    = MLEngine._safe_get(f, "cloud_cover_pct", 50.0)
        cape     = MLEngine._safe_get(f, "cape_jkg", 0.0)
        prev     = MLEngine._safe_get(f, "precipitation_lag_1h", 0.0)
        pres_dp  = MLEngine._safe_get(f, "pressure_change_3h", 0.0)

        z = (
            0.05 * (humidity - 70.0)
            - 0.22 * dew_dep
            + 0.02 * (cloud - 50.0)
            + 0.0015 * cape
            + 1.50 * (1.0 if prev > 0.1 else 0.0)
            - 0.30 * pres_dp               # falling pressure → more rain
        )
        return 1.0 / (1.0 + math.exp(-z))

    @staticmethod
    def _safe_get(d: dict[str, float], k: str, default: float) -> float:
        v = d.get(k, default)
        if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            return default
        try:
            return float(v)
        except (TypeError, ValueError):
            return default
