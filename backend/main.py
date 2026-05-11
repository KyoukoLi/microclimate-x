"""
FastAPI entry point for MicroClimate-X.

Endpoints
---------
GET  /                 — name / version / banner
GET  /api/predict      — main prediction endpoint (?lat=&lon=&activity=)
GET  /api/health       — JSON health + cache stats + DB latency
GET  /api/version      — version metadata for clients

Lifespan
--------
* On startup: WAL-mode SQLite init, prune expired cache rows, load ML model.
* On shutdown: dispose of the shared httpx.AsyncClient.

Resilience
----------
* `RequestIDMiddleware` stamps every request with `X-Request-ID` for log
  correlation (taken from incoming header if present, otherwise generated).
* All exceptions surface as a `errors.ErrorResponse` JSON document — no
  bare 500 HTML responses leak.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import logging
import math
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from . import cache, config, rule_engine, terrain
from .errors import (
    ERR_INTERNAL,
    ERR_INVALID_INPUT,
    ERR_UPSTREAM_FAILURE,
    ErrorResponse,
)
from .ml_engine import MLEngine
from .schemas import ActivityType, PredictionResponse

__version__ = "1.0.0"


# ──────────────────────────────────────────────────────────────────────────
# Logging — structured records: ts | level | request_id | message
# ──────────────────────────────────────────────────────────────────────────

class _RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True


_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)-7s | %(request_id)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
))
_handler.addFilter(_RequestIDFilter())
logging.basicConfig(level=logging.INFO, handlers=[_handler], force=True)
log = logging.getLogger("microclimate-x")


# ──────────────────────────────────────────────────────────────────────────
# Lifespan: model + DB + HTTP client
# ──────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting MicroClimate-X backend (v%s)…", __version__)
    await cache.init_db()
    pruned = await cache.prune_expired()
    if pruned:
        log.info("Cache GC removed %d expired rows on startup.", pruned)

    engine = MLEngine()
    engine.load()
    if engine.is_loaded:
        log.info("ML model loaded from %s", engine.loaded_from)
    else:
        log.warning(
            "No trained model found — falling back to heuristic predictor. "
            "Run scripts/3_train_model.py to enable Random Forest."
        )
    app.state.ml = engine
    app.state.http = httpx.AsyncClient(timeout=15.0, http2=False)
    app.state.start_ts = time.time()
    try:
        yield
    finally:
        await app.state.http.aclose()
        log.info("Shutdown complete.")


app = FastAPI(
    title="MicroClimate-X API",
    version=__version__,
    description=(
        "Hybrid microclimate risk assessment for complex terrain. "
        "Combines a Random Forest macro-rain predictor with a topographic "
        "rule-based expert system (Veto cascade + R1-R4 decision table "
        "+ activity-aware composite). "
        "Implements proposal §3.7 — sub-process P4.1 through P4.6."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time-ms"],
)


# ──────────────────────────────────────────────────────────────────────────
# Request-ID + timing middleware
# ──────────────────────────────────────────────────────────────────────────

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Tag every request with `X-Request-ID` and measure latency.

    The ID propagates from incoming headers (so a load-balancer / front-end
    can supply one) and falls back to a new UUID4 prefix.
    """

    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        # Stash on request state so handlers can read it.
        request.state.request_id = req_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:                                    # pragma: no cover
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            log.exception(
                "unhandled exception",
                extra={"request_id": req_id, "path": request.url.path,
                        "elapsed_ms": elapsed_ms},
            )
            return _json_error(
                req_id, 500, ERR_INTERNAL,
                "Internal server error — please retry.",
            )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        response.headers["X-Request-ID"]       = req_id
        response.headers["X-Response-Time-ms"] = str(elapsed_ms)
        # Only log non-static-asset, non-OPTIONS for noise control.
        if request.url.path.startswith("/api/") or request.url.path in {"/"}:
            log.info(
                "%s %s -> %d (%d ms)",
                request.method, request.url.path, response.status_code, elapsed_ms,
                extra={"request_id": req_id},
            )
        return response


app.add_middleware(RequestIDMiddleware)


# ──────────────────────────────────────────────────────────────────────────
# Exception handlers — every error follows the ErrorResponse schema
# ──────────────────────────────────────────────────────────────────────────

def _json_error(req_id: str | None, status: int, code: str, detail: str,
                ctx: dict[str, Any] | None = None) -> JSONResponse:
    payload = ErrorResponse(error=code, detail=detail, request_id=req_id, context=ctx)
    return JSONResponse(status_code=status, content=payload.model_dump(exclude_none=True))


@app.exception_handler(RequestValidationError)
async def _on_validation_error(request: Request, exc: RequestValidationError):
    req_id = getattr(request.state, "request_id", None)
    return _json_error(
        req_id, 422, ERR_INVALID_INPUT,
        "One or more query parameters failed validation.",
        ctx={"errors": exc.errors()[:5]},
    )


@app.exception_handler(HTTPException)
async def _on_http_exception(request: Request, exc: HTTPException):
    req_id = getattr(request.state, "request_id", None)
    code = (
        ERR_UPSTREAM_FAILURE if exc.status_code in {502, 503, 504}
        else ERR_INVALID_INPUT if exc.status_code in {400, 422}
        else ERR_INTERNAL
    )
    return _json_error(req_id, exc.status_code, code, str(exc.detail))


@app.exception_handler(Exception)
async def _on_unhandled(request: Request, exc: Exception):     # pragma: no cover
    req_id = getattr(request.state, "request_id", None)
    log.exception("unhandled top-level exception",
                  extra={"request_id": req_id or "-"})
    return _json_error(
        req_id, 500, ERR_INTERNAL,
        "Internal server error — please retry. If the problem persists, file an issue.",
    )


# ──────────────────────────────────────────────────────────────────────────
# Frontend static files (optional — only if /frontend exists alongside backend)
# ──────────────────────────────────────────────────────────────────────────

FRONTEND_DIR = config.ROOT / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


# ──────────────────────────────────────────────────────────────────────────
# Health & version & root
# ──────────────────────────────────────────────────────────────────────────

@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "name":         "MicroClimate-X",
        "version":      __version__,
        "ml_loaded":    app.state.ml.is_loaded,
        "frontend_url": "/app/",
        "docs_url":     "/docs",
        "openapi_url":  "/openapi.json",
    }


@app.get("/api/version")
async def version() -> dict[str, Any]:
    return {
        "version":        __version__,
        "git_revision":   config.GIT_REVISION,
        "ml_loaded":      app.state.ml.is_loaded,
        "ml_loaded_from": app.state.ml.loaded_from,
        "ml_features":    [*app.state.ml.feature_columns[:5], "…"]
                          if len(app.state.ml.feature_columns) > 5
                          else app.state.ml.feature_columns,
    }


@app.get("/api/health")
async def health() -> dict[str, Any]:
    stats = await cache.cache_stats()
    return {
        "status":          "ok",
        "uptime_sec":      int(time.time() - app.state.start_ts),
        "ml_loaded":       app.state.ml.is_loaded,
        "cache":           stats,
        "db_path":         str(config.DB_PATH),
        "version":         __version__,
    }


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

@app.get(
    "/api/predict",
    response_model=PredictionResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Invalid query parameters."},
        502: {"model": ErrorResponse, "description": "Upstream weather/DEM service failed."},
        500: {"model": ErrorResponse, "description": "Unexpected server error."},
    },
)
async def predict(
    request: Request,
    lat: float = Query(..., ge=-90.0,  le=90.0,  description="Latitude (WGS84)"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude (WGS84)"),
    activity: ActivityType = Query(
        "general",
        description="User activity context — affects composite score weighting (D5 §3.7 / P4.4).",
    ),
) -> PredictionResponse:
    req_id = getattr(request.state, "request_id", "-")

    # ── Cache lookup first (per-coordinate + per-activity) ──
    hit = await cache.get(lat, lon, activity=activity)
    if hit is not None:
        payload, ttl_remaining = hit
        payload["cached"] = True
        payload["cache_ttl"] = ttl_remaining
        log.info("cache hit (ttl_remaining=%ds)", ttl_remaining, extra={"request_id": req_id})
        return PredictionResponse(**payload)

    client: httpx.AsyncClient = app.state.http

    # ── Fetch DEM (terrain) and weather in parallel ──
    try:
        dem9, weather = await asyncio.gather(
            terrain.fetch_dem_3x3(lat, lon, client),
            _fetch_current_weather(client, lat, lon),
        )
    except (httpx.HTTPError, RetryError, ValueError) as exc:
        log.warning(
            "upstream API failure: %s",
            type(exc).__name__,
            extra={"request_id": req_id},
        )
        raise HTTPException(
            status_code=502,
            detail=f"Upstream weather/DEM service unavailable ({type(exc).__name__}). "
                   f"Please retry shortly.",
        ) from exc

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
    feats = _build_ml_features(weather, tinfo.elevation_m)

    try:
        ml_prob = app.state.ml.predict_rain_probability(feats)
    except Exception as exc:                                  # pragma: no cover
        log.exception("ML inference failed", extra={"request_id": req_id})
        raise HTTPException(
            status_code=500,
            detail=f"Model inference failed: {exc!r}",
        ) from exc

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

    # ── Cache + audit-log (fire-and-forget — never blocks the response) ──
    payload_dump = response.model_dump(mode="json")
    _bg_tasks: set[asyncio.Task[Any]] = getattr(request.app.state, "bg_tasks", None) or set()
    request.app.state.bg_tasks = _bg_tasks
    for coro in (
        cache.set(lat, lon, payload_dump, ttl, activity=activity),
        cache.log_inference(
            lat, lon, rule_result.risk_score, rule_result.has_veto,
            rule_result.advice_en,
        ),
    ):
        task = asyncio.create_task(coro)
        _bg_tasks.add(task)
        task.add_done_callback(_bg_tasks.discard)
    return response


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────

def _build_ml_features(weather: dict[str, Any], elevation_m: float) -> dict[str, float]:
    """Mirror of `scripts/2_preprocess.py` — keep features in sync with training."""
    now = _dt.datetime.now()
    feats = dict(weather)
    feats["elevation_m"] = elevation_m
    wind_kmh = weather.get("wind_speed_kmh", 0.0) or 0.0
    wind_dir = weather.get("wind_direction_deg", 0.0) or 0.0
    feats["wind_u"]    = wind_kmh * math.sin(math.radians(wind_dir))
    feats["wind_v"]    = wind_kmh * math.cos(math.radians(wind_dir))
    feats["hour_sin"]  = math.sin(2 * math.pi * now.hour  / 24.0)
    feats["hour_cos"]  = math.cos(2 * math.pi * now.hour  / 24.0)
    feats["month_sin"] = math.sin(2 * math.pi * now.month / 12.0)
    feats["month_cos"] = math.cos(2 * math.pi * now.month / 12.0)
    temp = weather.get("temperature_c") or 25.0
    dew  = weather.get("dew_point_c")   or temp
    feats["dew_point_depression"] = temp - dew
    feats["pressure_change_3h"]   = 0.0     # set by historical training; 0 at inference
    feats["precipitation_lag_1h"] = weather.get("precipitation_mm", 0.0) or 0.0
    return feats
