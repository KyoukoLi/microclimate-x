"""
HTTP integration tests — covers the FastAPI surface end-to-end.

External APIs (Open-Meteo, Open-Topo-Data) are mocked with `respx` so the
tests are hermetic and deterministic. We use a per-test temporary SQLite
DB via the `MICROCLIMATEX_DB` env override.
"""
from __future__ import annotations

import time as _t

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from backend import config
from backend.main import app

# ── helpers ──────────────────────────────────────────────────────────────

def _open_meteo_response(*, temp=22.0, humidity=88.0, wind=12.0,
                        wind_dir=240.0, pressure=1008.0, cape=200.0,
                        visibility=10000.0, precip=0.0, dew=20.0,
                        cloud=70.0) -> dict:
    return {
        "current": {
            "temperature_2m":         temp,
            "relative_humidity_2m":   humidity,
            "precipitation":          precip,
            "wind_speed_10m":         wind,
            "wind_direction_10m":     wind_dir,
            "surface_pressure":       pressure,
            "dew_point_2m":           dew,
            "cloud_cover":            cloud,
            "cape":                   cape,
            "visibility":             visibility,
        }
    }


def _open_topo_response(elevation_centre: float = 1800.0,
                        gradient: float = 30.0) -> dict:
    """Returns a 3x3 grid centred on `elevation_centre` with a gentle
    south-to-north gradient — produces 'Slope' classification."""
    rows = []
    for di in (+gradient, 0.0, -gradient):
        for dj in (-5.0, 0.0, +5.0):
            rows.append({"elevation": elevation_centre + di + dj})
    return {"results": rows}


@pytest.fixture
def client():
    """TestClient drives lifespan, so DB init + ML load happen automatically."""
    with TestClient(app) as c:
        yield c


# ── 1. Endpoint metadata ─────────────────────────────────────────────────

def test_root_returns_metadata(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "MicroClimate-X"
    assert "version" in body
    assert "ml_loaded" in body


def test_health_reports_cache_stats(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "cache" in body
    assert "rows_total" in body["cache"]
    assert "uptime_sec" in body


def test_version_endpoint_includes_git_revision(client):
    r = client.get("/api/version")
    assert r.status_code == 200
    body = r.json()
    assert "version" in body
    assert "git_revision" in body


def test_response_includes_request_id_and_timing(client):
    r = client.get("/api/health")
    assert "x-request-id" in r.headers
    assert "x-response-time-ms" in r.headers
    assert int(r.headers["x-response-time-ms"]) >= 0


def test_request_id_propagates_from_header(client):
    r = client.get("/api/health", headers={"X-Request-ID": "my-trace-1234"})
    assert r.headers["x-request-id"] == "my-trace-1234"


# ── 2. /api/predict — happy path with mocked upstreams ───────────────────

@respx.mock
def test_predict_happy_path_returns_full_schema(client):
    respx.get(config.OPEN_METEO_FORECAST_URL).mock(
        return_value=httpx.Response(200, json=_open_meteo_response())
    )
    respx.get(config.OPEN_TOPO_URL).mock(
        return_value=httpx.Response(200, json=_open_topo_response())
    )

    r = client.get("/api/predict?lat=3.4225&lon=101.7935&activity=hiker")
    assert r.status_code == 200
    body = r.json()
    # Schema sanity
    for key in (
        "latitude", "longitude", "elevation_m", "terrain",
        "ml_rain_probability", "hazard_subscores", "decision_table_matches",
        "activity", "risk_score", "risk_level", "veto_triggers",
        "inference_log", "advice_en", "advice_zh", "cached", "cache_ttl",
    ):
        assert key in body, f"missing field {key}"
    assert body["activity"] == "hiker"
    assert 0 <= body["risk_score"] <= 100
    assert 0.0 <= body["ml_rain_probability"] <= 1.0
    sub = body["hazard_subscores"]
    for k in ("rainfall", "fog", "wind_gust", "thunderstorm"):
        assert 0 <= sub[k] <= 100


@respx.mock
def test_predict_caches_on_repeat(client):
    respx.get(config.OPEN_METEO_FORECAST_URL).mock(
        return_value=httpx.Response(200, json=_open_meteo_response())
    )
    respx.get(config.OPEN_TOPO_URL).mock(
        return_value=httpx.Response(200, json=_open_topo_response())
    )

    a = client.get("/api/predict?lat=1.1&lon=110.0&activity=hiker").json()
    _t.sleep(0.2)  # let the fire-and-forget cache.set task finish
    b = client.get("/api/predict?lat=1.1&lon=110.0&activity=hiker").json()

    assert a["cached"] is False
    assert b["cached"] is True
    assert b["cache_ttl"] > 0
    assert a["risk_score"] == b["risk_score"]


@respx.mock
def test_predict_different_activity_different_cache_slot(client):
    respx.get(config.OPEN_METEO_FORECAST_URL).mock(
        return_value=httpx.Response(200, json=_open_meteo_response(
            cape=300.0, humidity=88.0,
        ))
    )
    respx.get(config.OPEN_TOPO_URL).mock(
        return_value=httpx.Response(200, json=_open_topo_response())
    )

    hiker = client.get("/api/predict?lat=2.0&lon=110.5&activity=hiker").json()
    _t.sleep(0.2)
    driver = client.get("/api/predict?lat=2.0&lon=110.5&activity=driver").json()
    # Both hit cache the SECOND time around — but each activity has its own slot.
    assert hiker["cached"] is False
    assert driver["cached"] is False


# ── 3. /api/predict — error paths ────────────────────────────────────────

def test_predict_invalid_lat_returns_422(client):
    r = client.get("/api/predict?lat=999&lon=0")
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "invalid_input"
    assert "request_id" in body


def test_predict_invalid_activity_returns_422(client):
    r = client.get("/api/predict?lat=3.0&lon=101.0&activity=astronaut")
    assert r.status_code == 422


@respx.mock
def test_predict_upstream_failure_returns_502(client):
    respx.get(config.OPEN_METEO_FORECAST_URL).mock(
        return_value=httpx.Response(503)
    )
    respx.get(config.OPEN_TOPO_URL).mock(
        return_value=httpx.Response(200, json=_open_topo_response())
    )

    r = client.get("/api/predict?lat=5.5&lon=100.5")
    assert r.status_code == 502
    body = r.json()
    assert body["error"] == "upstream_failure"
    assert "request_id" in body


# ── 4. CORS preflight ────────────────────────────────────────────────────

def test_cors_allow_origin_wildcard(client):
    r = client.get("/api/health", headers={"Origin": "https://example.com"})
    assert r.headers.get("access-control-allow-origin") == "*"


# ── 5. OpenAPI schema is valid + documents error responses ───────────────

def test_openapi_schema_lists_predict_error_responses(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    predict = spec["paths"]["/api/predict"]["get"]["responses"]
    for code in ("200", "422", "502"):
        assert code in predict
