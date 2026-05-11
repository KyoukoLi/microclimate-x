"""
Tests for the D5-proposal-aligned extensions:

    1. Four hazard sub-scorers (P4.3)
    2. Decision Table R1-R4 (D5 §3.7.2 / Table 4.2)
    3. Activity-aware weighting (P4.4)
    4. Composite-score formula (P4.5)
"""
from __future__ import annotations

import pytest

from backend import rule_engine
from backend.schemas import HazardSubscores


def _base_weather(**ov):
    base = {
        "temperature_c": 25.0,
        "humidity_pct": 70.0,
        "wind_speed_kmh": 8.0,
        "wind_direction_deg": 180.0,
        "pressure_hpa": 1010.0,
        "cape_jkg": 0.0,
        "visibility_m": 10000.0,
        "pressure_change_3h": 0.0,
        "dew_point_depression": 5.0,
        "cloud_cover_pct": 50.0,
    }
    base.update(ov)
    return base


# ════════════════════════════════════════════════════════════════════════
# P4.3 — Four hazard sub-scorers
# ════════════════════════════════════════════════════════════════════════

def test_fog_subscore_fires_on_saturated_valley():
    s = rule_engine.score_fog_risk(
        humidity_pct=98.0, dew_point_depression=0.6,
        cloud_cover_pct=95.0, terrain="Valley", elevation_m=400.0,
    )
    assert s >= 70, f"saturated valley should be high fog risk, got {s}"


def test_fog_subscore_zero_on_dry_day():
    s = rule_engine.score_fog_risk(
        humidity_pct=45.0, dew_point_depression=15.0,
        cloud_cover_pct=10.0, terrain="Flat", elevation_m=100.0,
    )
    assert s < 10


def test_wind_gust_subscore_amplified_on_ridge():
    s_ridge = rule_engine.score_wind_gust_risk(
        wind_speed_kmh=30.0, terrain="Peak",
        slope_deg=25.0, orographic_dot=0.6,
    )
    s_flat = rule_engine.score_wind_gust_risk(
        wind_speed_kmh=30.0, terrain="Flat",
        slope_deg=1.0, orographic_dot=0.0,
    )
    assert s_ridge > s_flat + 20, "ridge should amplify gust risk vs flat"


def test_thunderstorm_subscore_on_high_cape_falling_pressure():
    s = rule_engine.score_thunderstorm_risk(
        cape_jkg=1500.0, pressure_change_3h=-3.0, humidity_pct=85.0,
    )
    assert s >= 70


def test_rainfall_subscore_calibration_at_45_percent_prob():
    """45% probability on flat terrain should land in the Caution band when
    combined with the activity-weighting layer."""
    s = rule_engine.score_rainfall_risk(
        ml_rain_prob=0.45, terrain="Flat", orographic_dot=0.0,
        pressure_change_3h=0.0, humidity_pct=70.0,
    )
    assert 30 <= s <= 55, f"45 % rain prob → expected ~40, got {s}"


# ════════════════════════════════════════════════════════════════════════
# D5 §3.7.2 — Decision Table R1-R4
# ════════════════════════════════════════════════════════════════════════

def test_decision_table_R1_hidden_rain_on_windward_slope():
    """R1: macro ≤ 30% but humid + windward slope + falling pressure → hidden rain."""
    matches = rule_engine.apply_decision_table_3_7_2(
        macro_rain_prob=0.20,
        humidity_pct=92.0,
        wind_into_slope=True,
        terrain="Slope",
        pressure_change_3h=-2.5,
        cloud_base_m=500.0,
    )
    rules = {m.rule for m in matches}
    assert "R1" in rules


def test_decision_table_R2_no_amplification_on_leeward():
    matches = rule_engine.apply_decision_table_3_7_2(
        macro_rain_prob=0.20,
        humidity_pct=92.0,
        wind_into_slope=False,
        terrain="Valley",
        pressure_change_3h=-2.5,
        cloud_base_m=500.0,
    )
    rules = {m.rule for m in matches}
    assert "R2" in rules


def test_decision_table_R3_heavy_downpour_on_windward_slope():
    matches = rule_engine.apply_decision_table_3_7_2(
        macro_rain_prob=0.80,
        humidity_pct=70.0,
        wind_into_slope=True,
        terrain="Slope",
        pressure_change_3h=0.0,
        cloud_base_m=None,
    )
    rules = {m.rule for m in matches}
    assert "R3" in rules


def test_decision_table_R4_normal_rain_flat_terrain():
    matches = rule_engine.apply_decision_table_3_7_2(
        macro_rain_prob=0.85,
        humidity_pct=75.0,
        wind_into_slope=False,
        terrain="Flat",
        pressure_change_3h=0.0,
        cloud_base_m=None,
    )
    rules = {m.rule for m in matches}
    assert "R4" in rules


# ════════════════════════════════════════════════════════════════════════
# P4.4 — Activity-aware weighting
# ════════════════════════════════════════════════════════════════════════

def _subs(rain=0, fog=0, gust=0, thunder=0) -> HazardSubscores:
    return HazardSubscores(
        rainfall=rain, fog=fog, wind_gust=gust, thunderstorm=thunder,
    )


def test_hiker_more_sensitive_to_thunderstorm_than_driver():
    subs = _subs(rain=20, fog=20, gust=20, thunder=70)
    s_hiker  = rule_engine.apply_activity_weighting(subs, activity="hiker")
    s_driver = rule_engine.apply_activity_weighting(subs, activity="driver")
    assert s_hiker > s_driver


def test_driver_more_sensitive_to_fog_than_general():
    subs = _subs(rain=10, fog=70, gust=10, thunder=10)
    s_driver  = rule_engine.apply_activity_weighting(subs, activity="driver")
    s_general = rule_engine.apply_activity_weighting(subs, activity="general")
    assert s_driver > s_general


def test_construction_more_sensitive_to_wind_than_hiker():
    subs = _subs(rain=10, fog=10, gust=70, thunder=10)
    s_cons   = rule_engine.apply_activity_weighting(subs, activity="construction")
    s_hiker  = rule_engine.apply_activity_weighting(subs, activity="hiker")
    assert s_cons > s_hiker


def test_composite_dominated_by_top_hazard():
    """Composite should be close to the maximum sub-score, not the mean."""
    subs = _subs(rain=90, fog=0, gust=0, thunder=0)
    s = rule_engine.apply_activity_weighting(subs, activity="general")
    assert s >= 70, f"single 90 hazard should dominate, got {s}"


def test_composite_clipped_to_100():
    subs = _subs(rain=100, fog=100, gust=100, thunder=100)
    s = rule_engine.apply_activity_weighting(subs, activity="hiker")
    assert s == 100


# ════════════════════════════════════════════════════════════════════════
# Top-level integration via evaluate()
# ════════════════════════════════════════════════════════════════════════

def test_evaluate_includes_hazard_subscores():
    res = rule_engine.evaluate(
        lat=3.0, lon=101.5,
        elevation_m=400.0,
        terrain="Valley",
        weather=_base_weather(humidity_pct=98.0, dew_point_depression=0.5,
                              cloud_cover_pct=95.0),
        ml_rain_prob=0.10,
        slope_deg=2.0, aspect_deg=0.0, orographic_dot=0.0,
        activity="hiker",
    )
    # Fog should clearly dominate in this scenario.
    assert res.hazard_subscores.fog > res.hazard_subscores.rainfall
    assert res.hazard_subscores.fog > res.hazard_subscores.wind_gust
    assert res.hazard_subscores.fog > res.hazard_subscores.thunderstorm
    assert res.activity == "hiker"


def test_evaluate_same_scenario_different_activity_yields_different_score():
    # CAPE below HIGH_CAPE_JKG (1000) to avoid the Veto cap → activity still matters.
    weather = _base_weather(cape_jkg=700.0, pressure_change_3h=-3.0,
                            humidity_pct=85.0)
    s_hiker = rule_engine.evaluate(
        lat=3.0, lon=101.5, elevation_m=400.0, terrain="Slope",
        weather=weather, ml_rain_prob=0.3,
        slope_deg=10.0, aspect_deg=0.0, orographic_dot=0.2,
        activity="hiker",
    ).risk_score
    s_driver = rule_engine.evaluate(
        lat=3.0, lon=101.5, elevation_m=400.0, terrain="Slope",
        weather=weather, ml_rain_prob=0.3,
        slope_deg=10.0, aspect_deg=0.0, orographic_dot=0.2,
        activity="driver",
    ).risk_score
    # Thunderstorm-heavy scenario should affect hiker more.
    assert s_hiker != s_driver


def test_decision_table_match_emits_inference_log_line():
    res = rule_engine.evaluate(
        lat=3.0, lon=101.5,
        elevation_m=1000.0,
        terrain="Slope",
        weather=_base_weather(humidity_pct=92.0, pressure_change_3h=-2.5,
                              cloud_cover_pct=95.0, dew_point_depression=1.0),
        ml_rain_prob=0.20,
        slope_deg=15.0, aspect_deg=270.0, orographic_dot=0.5,
        activity="hiker",
    )
    table_log_lines = [s for s in res.inference_log if s.kind == "table"]
    # At least one R1-R4 match should have fired and been logged.
    assert len(table_log_lines) >= 1
    assert len(res.decision_table_matches) >= 1
