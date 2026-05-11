"""Tests for backend.ml_engine — fallback heuristic and load resilience."""
from __future__ import annotations

import math

import pytest

from backend.ml_engine import MLEngine


def test_engine_starts_unloaded_when_no_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.ml_engine.config.MODEL_DIR", tmp_path)
    e = MLEngine()
    e.load()
    assert e.is_loaded is False
    assert e.loaded_from is None


def test_fallback_heuristic_returns_probability_in_range():
    e = MLEngine()
    e.load()  # no model → fallback
    p = e.predict_rain_probability({
        "humidity_pct": 70, "dew_point_depression": 5, "cloud_cover_pct": 50,
        "cape_jkg": 0, "precipitation_lag_1h": 0, "pressure_change_3h": 0,
    })
    assert 0.0 <= p <= 1.0


def test_fallback_heuristic_higher_when_humid_and_recent_rain():
    e = MLEngine()
    e.load()
    dry = e.predict_rain_probability({
        "humidity_pct": 40, "dew_point_depression": 10,
        "cloud_cover_pct": 10, "cape_jkg": 0, "precipitation_lag_1h": 0,
    })
    wet = e.predict_rain_probability({
        "humidity_pct": 95, "dew_point_depression": 1,
        "cloud_cover_pct": 90, "cape_jkg": 800, "precipitation_lag_1h": 2.0,
    })
    assert wet > dry + 0.3


def test_fallback_heuristic_responds_to_pressure_drop():
    e = MLEngine()
    e.load()
    stable = e.predict_rain_probability({
        "humidity_pct": 80, "dew_point_depression": 3,
        "cloud_cover_pct": 70, "pressure_change_3h": 0.0,
    })
    falling = e.predict_rain_probability({
        "humidity_pct": 80, "dew_point_depression": 3,
        "cloud_cover_pct": 70, "pressure_change_3h": -3.0,
    })
    assert falling > stable


def test_safe_feat_handles_nan_and_none():
    assert MLEngine._safe_feat({"x": float("nan")}, "x") == 0.0
    assert MLEngine._safe_feat({"x": None}, "x") == 0.0
    assert MLEngine._safe_feat({"x": "garbage"}, "x") == 0.0
    assert MLEngine._safe_feat({}, "x") == 0.0
    assert MLEngine._safe_feat({"x": 3.14}, "x") == 3.14


def test_safe_get_returns_default_for_invalid_types():
    assert MLEngine._safe_get({}, "k", 5.0) == 5.0
    assert MLEngine._safe_get({"k": None}, "k", 5.0) == 5.0
    assert MLEngine._safe_get({"k": float("inf")}, "k", 5.0) == 5.0
    assert MLEngine._safe_get({"k": 1.5}, "k", 5.0) == 1.5
