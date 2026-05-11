"""
FastAPI entry point for MicroClimate-X.

Endpoints
---------
GET  /                 — health check + project banner
GET  /api/predict      — main prediction endpoint (?lat=&lon=)
GET  /api/health       — JSON health + cache stats

Lifespan
--------
* On startup: WAL-mode SQLite init + load ML model once.
* On shutdown: dispose of the shared httpx.AsyncClient.
"""
from __future__ import annotations

import asyncio
import logging
import math
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from tenacity import retry, stop_after_attempt, wait_exponential

from . import cache, config, rule_engine, terrain
from .ml_engine import MLEngine
from .schemas import (
    ActivityType,
    PredictionResponse,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("microclimate-x")


# ──────────────────────────────────────────────────────────────────────────
# Lifespan: model + DB + HTTP client
# ──────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting MicroClimate-X backend…")
    await cache.init_db()

    engine = MLEngine()
    engine.load()
    if engine.is_loaded:
        log.info(f"ML model loaded from {engine.loaded_from}")
    else:
        log.warning("No trained model found — falling back to heuristic predictor. "
                    "Run scripts/3_train_model.py to enable Random Forest.")
    app.state.ml = engine
    app.state.http = httpx.AsyncClient(timeout=15.0)
    try:
        yield
    finally:
        await app.state.http.aclose()
        log.info("Shutdown complete.")


app = FastAPI(
    title="MicroClimate-X API",
    version="0.1.0",
    description="Hybrid microclimate risk assessment for complex terrain.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# Serve the bundled SPA at /app
FRONTEND_DIR = config.ROOT / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


# ──────────────────────────────────────────────────────────────────────────
# Health & root
# ──────────────────────────────────────────────────────────────────────────

@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "name": "MicroClimate-X",
        "version": app.version,
        "ml_loaded": app.state.ml.is_loaded,
        "frontend_url": "/app/",
        "docs_url": "/docs",
    }


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "ml_loaded": app.state.ml.is_loaded}


# ──────────────────────────────────────────────────────────────────────────
# External fetching helpers
# ──────────────────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def _fetch_current_weather(client: httpx.AsyncClient, lat: float, lon: float) -> dict[str, Any]:
    resp = await client.get(
        config.OPEN_METEO_FORECAST_URL,
        params={
            "latitude":  lat,
            "longitude": lon,
            "current":   ",".join([
                "temperature_2m", "relative_humidity_2m", "precipitation",
                "wind_speed_10m", "wind_direction_10m", "surface_pressure",
                "dew_point_2m", "cloud_cover", "cape", "visibility",
            ]),
            "windspeed_unit": "kmh",
            "timezone": "auto",
        },
        timeout=15.0,
    )
    resp.raise_for_status()
    raw = resp.json().get("current", {})
    return {
        "temperature_c":         raw.get("temperature_2m"),
        "humidity_pct":          raw.get("relative_humidity_2m"),
        "precipitation_mm":      raw.get("precipitation", 0.0),
        "wind_speed_kmh":        raw.get("wind_speed_10m", 0.0),
        "wind_direction_deg":    raw.get("wind_direction_10m", 0.0),
        "pressure_hpa":          raw.get("surface_pressure"),
        "dew_point_c":           raw.get("dew_point_2m"),
        "cloud_cover_pct":       raw.get("cloud_cover", 0.0),
        "cape_jkg":              raw.get("cape", 0.0),
        "visibility_m":          raw.get("visibility", 10000.0),
    }


# ──────────────────────────────────────────────────────────────────────────
# Main endpoint
# ──────────────────────────────────────────────────────────────────────────

@app.get("/api/predict", response_model=PredictionResponse)
async def predict(
    lat: float = Query(..., ge=-90.0,  le=90.0,  description="Latitude (WGS84)"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude (WGS84)"),
    activity: ActivityType = Query(
        "general",
        description="User activity context — affects composite-score weighting (D5 §3.7 / P4.4)",
    ),
) -> PredictionResponse:
    # ── Cache lookup first (per-coordinate + per-activity) ──
    hit = await cache.get(lat, lon, activity=activity)
    if hit is not None:
        payload, ttl_remaining = hit
        payload["cached"] = True
        payload["cache_ttl"] = ttl_remaining
        return PredictionResponse(**payload)

    client: httpx.AsyncClient = app.state.http

    # ── Fetch DEM (terrain) and weather in parallel ──
    try:
        dem9, weather = await asyncio.gather(
            terrain.fetch_dem_3x3(lat, lon, client),
            _fetch_current_weather(client, lat, lon),
        )
    except httpx.HTTPError as exc:
        log.exception("External API failure")
        raise HTTPException(status_code=502, detail=f"Upstream weather/DEM service failed: {exc}")

    tinfo = terrain.classify_terrain(dem9)

    orographic_dot = (
        terrain.orographic_lift_dot(
            weather.get("wind_direction_deg", 0.0),
            tinfo.aspect_deg,
            tinfo.slope_deg,
        )
        if tinfo.terrain == "Slope" else 0.0
    )

    # ── Build ML feature dict ──
    import datetime as _dt
    now = _dt.datetime.now()
    feats = dict(weather)
    feats["elevation_m"] = tinfo.elevation_m
    feats["wind_u"] = weather["wind_speed_kmh"] * math.sin(math.radians(weather["wind_direction_deg"]))
    feats["wind_v"] = weather["wind_speed_kmh"] * math.cos(math.radians(weather["wind_direction_deg"]))
    feats["hour_sin"]  = math.sin(2 * math.pi * now.hour  / 24.0)
    feats["hour_cos"]  = math.cos(2 * math.pi * now.hour  / 24.0)
    feats["month_sin"] = math.sin(2 * math.pi * now.month / 12.0)
    feats["month_cos"] = math.cos(2 * math.pi * now.month / 12.0)
    feats["dew_point_depression"] = feats["temperature_c"] - feats.get("dew_point_c", feats["temperature_c"])
    feats["pressure_change_3h"]   = 0.0
    feats["precipitation_lag_1h"] = weather.get("precipitation_mm", 0.0)

    ml_prob = app.state.ml.predict_rain_probability(feats)

    # ── Apply Rule Engine ──
    rule_result = rule_engine.evaluate(
        lat=lat,
        lon=lon,
        elevation_m=tinfo.elevation_m,
        terrain=tinfo.terrain,
        weather=weather,
        ml_rain_prob=ml_prob,
        slope_deg=tinfo.slope_deg,
        aspect_deg=tinfo.aspect_deg,
        orographic_dot=orographic_dot,
        activity=activity,
    )

    # ── Assemble response ──
    ttl = cache.adaptive_ttl(rule_result.risk_score, rule_result.has_veto)
    response = PredictionResponse(
        latitude=lat,
        longitude=lon,
        elevation_m=tinfo.elevation_m,
        terrain=tinfo.terrain,
        ml_rain_probability=ml_prob,
        hazard_subscores=rule_result.hazard_subscores,
        decision_table_matches=rule_result.decision_table_matches,
        activity=rule_result.activity,
        risk_score=rule_result.risk_score,
        risk_level=rule_result.risk_level,
        veto_triggers=rule_result.veto_triggers,
        inference_log=rule_result.inference_log,
        advice_en=rule_result.advice_en,
        advice_zh=rule_result.advice_zh,
        cached=False,
        cache_ttl=ttl,
    )

    # ── Cache + audit-log ──
    await cache.set(lat, lon, response.model_dump(mode="json"), ttl,
                    activity=activity)
    await cache.log_inference(
        lat, lon, rule_result.risk_score, rule_result.has_veto,
        rule_result.advice_en,
    )
    return response
