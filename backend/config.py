"""
Central configuration for MicroClimate-X.

EVERY Veto threshold below has an academic / regulatory citation.
This is intentional — at thesis defence the panel WILL ask
"why 3500 m, why -5 °C, why 40 km/h?". Be ready to point to this file.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "models"
DATA_DIR  = ROOT / "data"
DB_PATH   = ROOT / "cache.sqlite3"


# ──────────────────────────────────────────────────────────────────────────
# Veto thresholds — one-vote rejection rules
# ──────────────────────────────────────────────────────────────────────────
# Citation: Luks et al. (2019) "Wilderness Medical Society Practice
#           Guidelines for the Prevention and Treatment of Acute Altitude
#           Illness." High altitude (>2500 m) carries clinical risk; severe
#           hypoxia onset is well-documented above ~3500 m.
ALTITUDE_HYPOXIA_M = 3500.0

# Citation: WMO Beaufort scale — Force 6 "Strong breeze" ≈ 39-49 km/h,
#           the threshold above which outdoor activity becomes hazardous.
GALE_WIND_KMH = 40.0

# Citation: UIAA Medical Commission frostbite risk guidance — exposed skin
#           freezes rapidly below approximately -5 °C with wind chill.
EXTREME_COLD_C = -5.0

# Citation: U.S. NWS convective forecasting handbook — CAPE > 1000 J/kg
#           indicates moderate-to-strong instability suitable for
#           thunderstorm development.
HIGH_CAPE_JKG = 1000.0

# Citation: FAA AIM 7-1-12 — visibility below 100 m is classified as
#           Category III instrument-only conditions. Used here as an extreme
#           low-visibility threshold (whiteout / dense fog).
LOW_VISIBILITY_M = 100.0

# Wind alignment with slope normal vector (orographic uplift). The
# threshold 0.7 corresponds to ~45 degrees of slope-facing wind.
OROGRAPHIC_DOT_THRESHOLD = 0.7

# Wet-flood trigger in a valley basin: high probability of localised rain
# combined with valley-floor topography.
VALLEY_FLOOD_PROB = 0.80


# ──────────────────────────────────────────────────────────────────────────
# Risk scoring (additive penalties when no Veto fires)
# ──────────────────────────────────────────────────────────────────────────
PENALTY = {
    "ml_high_rain_prob": 35,   # ML predicts >= 70 % rain probability
    "ml_mid_rain_prob":  15,   # ML predicts 40-70 % rain probability
    "valley_floor":      10,
    "windward_slope":    20,
    "orographic_lift":   25,
    "altitude_high":     15,   # 2500-3500 m, sub-Veto altitude band
    "wind_strong":       10,   # 25-40 km/h
}


# ──────────────────────────────────────────────────────────────────────────
# Four hazard categories — matches D5 proposal §3.7 / P4.3
# ──────────────────────────────────────────────────────────────────────────
# Fog risk:
#   WMO surface synoptic code: fog ≈ visibility < 1 km, RH typically > 95 %,
#   dew-point depression < ~2 °C. Valley/Slope basins trap radiation fog.
FOG_HUMIDITY_PCT      = 95.0
FOG_DEW_DEP_MAX_C     = 2.0
FOG_CLOUD_BASE_MAX_M  = 800.0    # from D5 §3.7.2 decision table

# Wind gust risk:
#   On exposed ridges and mountain passes, sustained 25 km/h winds with
#   topographic acceleration commonly gust to Beaufort F6 levels.
GUST_WIND_MIN_KMH     = 25.0     # below GALE_WIND_KMH but still risky

# Thunderstorm risk:
#   NWS "moderate instability" begins at CAPE 500 J/kg; sharp pressure drop
#   often precedes convective initiation.
THUNDER_CAPE_MIN_JKG  = 500.0
THUNDER_PRESSURE_DROP = -2.0     # hPa over past 3 h (matches D5 §1.3 example)


# ──────────────────────────────────────────────────────────────────────────
# Decision Table — D5 §3.7.2 / Table 4.2  (one-to-one with the thesis)
# ──────────────────────────────────────────────────────────────────────────
# Each rule fires when ALL of its non-None conditions hold. The thesis
# narrative motivates this table as: "macro forecast says no rain, but
# the local terrain conditions imply hidden risk".
DECISION_TABLE_3_7_2 = {
    "R1": {
        "description":            "Hidden rain risk — macro says no, terrain says yes",
        "macro_rain_prob_max":    0.30,
        "macro_rain_prob_min":    None,
        "humidity_min_pct":       85.0,
        "wind_into_slope":        True,
        "terrain":                "WindwardSlope",
        "pressure_change_3h_max": -1.5,
        "cloud_base_max_m":       FOG_CLOUD_BASE_MAX_M,
        "conclusion_en":          "Hidden rain risk: terrain analysis indicates orographic precipitation despite low macro probability.",
        "conclusion_zh":          "隐藏降雨风险：宏观预报概率低，但地形分析表明存在地形抬升降水。",
    },
    "R2": {
        "description":            "No significant risk — terrain not aligned",
        "macro_rain_prob_max":    0.30,
        "macro_rain_prob_min":    None,
        "humidity_min_pct":       85.0,
        "wind_into_slope":        False,
        "terrain":                "LeewardOrValley",
        "pressure_change_3h_max": -1.5,
        "cloud_base_max_m":       FOG_CLOUD_BASE_MAX_M,
        "conclusion_en":          "No significant rainfall danger at this spot in this period.",
        "conclusion_zh":          "此地此时无显著降雨危险。",
    },
    "R3": {
        "description":            "Heavy downpour incoming — avoid exposure",
        "macro_rain_prob_max":    None,
        "macro_rain_prob_min":    0.70,
        "humidity_min_pct":       None,
        "wind_into_slope":        True,
        "terrain":                "WindwardSlope",
        "pressure_change_3h_max": None,
        "cloud_base_max_m":       None,
        "conclusion_en":          "Heavy downpour incoming. Avoid mountains and valleys.",
        "conclusion_zh":          "强降雨即将到来。请避开山区与峡谷。",
    },
    "R4": {
        "description":            "Normal rain — no terrain amplification",
        "macro_rain_prob_max":    None,
        "macro_rain_prob_min":    0.70,
        "humidity_min_pct":       None,
        "wind_into_slope":        None,
        "terrain":                None,
        "pressure_change_3h_max": None,
        "cloud_base_max_m":       None,
        "conclusion_en":          "Rain expected, but no terrain-induced amplification. Standard rain precautions apply.",
        "conclusion_zh":          "预计有雨，但无地形抬升放大。按一般雨天措施应对即可。",
    },
}


# ──────────────────────────────────────────────────────────────────────────
# Activity-aware weighting — D5 §3.7 / P4.4
# ──────────────────────────────────────────────────────────────────────────
# Composite = Σ w_i · subscore_i, then renormalised to 0-100.
# Rows: activity. Cols: rainfall, fog, wind_gust, thunderstorm.
ACTIVITY_WEIGHTS = {
    "hiker":        {"rainfall": 1.0, "fog": 1.3, "wind_gust": 1.0, "thunderstorm": 1.4},
    "driver":       {"rainfall": 0.8, "fog": 1.5, "wind_gust": 1.3, "thunderstorm": 0.9},
    "construction": {"rainfall": 1.0, "fog": 0.8, "wind_gust": 1.5, "thunderstorm": 1.4},
    "general":      {"rainfall": 1.0, "fog": 1.0, "wind_gust": 1.0, "thunderstorm": 1.0},
}


# ──────────────────────────────────────────────────────────────────────────
# Cache TTL (risk-adaptive)
# ──────────────────────────────────────────────────────────────────────────
# Safety-critical apps must not serve stale "Safe" verdicts during developing
# storms. Bucket TTL by risk band.
TTL_HIGH_RISK_SEC = 60      # any Veto fired OR risk >= 70
TTL_MID_RISK_SEC  = 300     # risk 40-70
TTL_LOW_RISK_SEC  = 600     # risk < 40

# Grid resolution used as cache key (0.01° ≈ 1.1 km at the equator).
GRID_RESOLUTION_DEG = 0.01


# ──────────────────────────────────────────────────────────────────────────
# External API endpoints
# ──────────────────────────────────────────────────────────────────────────
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_TOPO_URL           = "https://api.opentopodata.org/v1/srtm30m"


# ──────────────────────────────────────────────────────────────────────────
# Domain constants
# ──────────────────────────────────────────────────────────────────────────
# WMO definition of trace precipitation.
RAIN_THRESHOLD_MM = 0.1
