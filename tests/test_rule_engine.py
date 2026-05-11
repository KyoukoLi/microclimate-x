"""
Unit tests for the rule-based safety engine.

These tests exist primarily to defend the thesis claim that the system
catches dangerous out-of-distribution scenarios (e.g. Mt Everest) that a
pure-ML model would happily misclassify as "safe".
"""
from __future__ import annotations

import pytest

from backend import config, rule_engine


def _base_weather(**overrides):
    base = {
        "temperature_c": 25.0,
        "humidity_pct": 70.0,
        "wind_speed_kmh": 8.0,
        "wind_direction_deg": 180.0,
        "pressure_hpa": 1010.0,
        "cape_jkg": 0.0,
        "visibility_m": 10000.0,
    }
    base.update(overrides)
    return base


def test_safe_baseline_genting_highlands():
    """Calm tropical afternoon at Genting (~1800 m) — should be Safe/Caution."""
    res = rule_engine.evaluate(
        lat=3.4225, lon=101.7935,
        elevation_m=1865.0,
        terrain="Slope",
        weather=_base_weather(),
        ml_rain_prob=0.20,
        slope_deg=8.0,
        aspect_deg=270.0,
        orographic_dot=0.1,
    )
    assert not res.has_veto
    assert res.risk_score < 50
    assert res.risk_level in {"Safe", "Caution"}


def test_mt_everest_veto_hypoxia():
    """The flagship OOD example: ML says no rain, rules MUST still flag danger."""
    res = rule_engine.evaluate(
        lat=27.9881, lon=86.9250,
        elevation_m=8848.0,
        terrain="Peak",
        weather=_base_weather(temperature_c=-30.0, wind_speed_kmh=80.0),
        ml_rain_prob=0.01,
        slope_deg=40.0,
        aspect_deg=180.0,
        orographic_dot=0.0,
    )
    assert res.has_veto
    veto_rules = {v.rule for v in res.veto_triggers}
    assert "altitude_hypoxia" in veto_rules
    assert "extreme_cold" in veto_rules
    assert "gale_wind" in veto_rules
    assert res.risk_score == 100
    assert res.risk_level == "Danger"


def test_valley_flash_flood_veto():
    """High rain probability + valley terrain should trip the flash-flood veto."""
    res = rule_engine.evaluate(
        lat=3.0, lon=101.5,
        elevation_m=500.0,
        terrain="Valley",
        weather=_base_weather(),
        ml_rain_prob=0.92,
        slope_deg=2.0,
        aspect_deg=0.0,
        orographic_dot=0.0,
    )
    assert any(v.rule == "valley_flash_flood" for v in res.veto_triggers)
    assert res.risk_score == 100


def test_orographic_uplift_veto():
    """Wind blowing straight into a slope with high rain prob triggers veto."""
    res = rule_engine.evaluate(
        lat=4.5, lon=101.4,
        elevation_m=1200.0,
        terrain="Slope",
        weather=_base_weather(wind_speed_kmh=15.0),
        ml_rain_prob=0.65,
        slope_deg=20.0,
        aspect_deg=90.0,
        orographic_dot=0.9,
    )
    assert any(v.rule == "orographic_lift_storm" for v in res.veto_triggers)


def test_caution_band_threshold():
    """Mid-probability rain in mild terrain produces Caution, not Warning."""
    res = rule_engine.evaluate(
        lat=3.0, lon=101.5,
        elevation_m=150.0,
        terrain="Flat",
        weather=_base_weather(),
        ml_rain_prob=0.45,
        slope_deg=1.0,
        aspect_deg=0.0,
        orographic_dot=0.0,
    )
    assert not res.has_veto
    assert 30 <= res.risk_score < 55
    assert res.risk_level == "Caution"


def test_bilingual_advice_present():
    """Both EN and ZH advice strings must always be populated."""
    res = rule_engine.evaluate(
        lat=3.0, lon=101.5,
        elevation_m=100.0,
        terrain="Flat",
        weather=_base_weather(),
        ml_rain_prob=0.10,
        slope_deg=1.0,
        aspect_deg=0.0,
        orographic_dot=0.0,
    )
    assert res.advice_en and res.advice_zh
    assert isinstance(res.advice_en, str)
    assert isinstance(res.advice_zh, str)


def test_inference_log_includes_ml_step():
    res = rule_engine.evaluate(
        lat=3.0, lon=101.5,
        elevation_m=100.0,
        terrain="Flat",
        weather=_base_weather(),
        ml_rain_prob=0.30,
        slope_deg=1.0,
        aspect_deg=0.0,
        orographic_dot=0.0,
    )
    kinds = [s.kind for s in res.inference_log]
    assert "ml" in kinds
    assert "score" in kinds


@pytest.mark.parametrize("score,expected", [
    (0, "Safe"), (29, "Safe"),
    (30, "Caution"), (54, "Caution"),
    (55, "Warning"), (79, "Warning"),
    (80, "Danger"), (100, "Danger"),
])
def test_bin_level_boundaries(score, expected):
    assert rule_engine._bin_level(score) == expected
