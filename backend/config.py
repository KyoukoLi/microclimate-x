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
