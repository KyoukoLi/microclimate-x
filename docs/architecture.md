# Architecture / 架构

## Request flow / 请求流程

```
┌──────────────┐ 1. click(lat,lon)  ┌──────────────────────────────┐
│   Browser    │ ─────────────────► │  FastAPI  /api/predict        │
│  Vue3 + Map  │                    │                               │
└──────────────┘ ◄───────────────── │  ┌─────────────────────────┐  │
                  6. JSON response  │  │  Cache lookup           │  │
                                    │  │  (WAL SQLite, 60-600s)  │  │
                                    │  └────────┬────────────────┘  │
                                    │           │ miss              │
                                    │           ▼                   │
                                    │  ┌─────────────────────────┐  │
                                    │  │ 2. Parallel fetch       │  │
                                    │  │  - Open-Meteo (weather) │  │
                                    │  │  - Open-Topo-Data (DEM) │  │
                                    │  └────────┬────────────────┘  │
                                    │           ▼                   │
                                    │  ┌─────────────────────────┐  │
                                    │  │ 3. Engine A — RandomFor │  │
                                    │  │    predict_proba → P    │  │
                                    │  └────────┬────────────────┘  │
                                    │           ▼                   │
                                    │  ┌─────────────────────────┐  │
                                    │  │ 4. Engine B — Rules     │  │
                                    │  │    Veto + score 0-100   │  │
                                    │  │    Bilingual advice     │  │
                                    │  └────────┬────────────────┘  │
                                    │           ▼                   │
                                    │  ┌─────────────────────────┐  │
                                    │  │ 5. Cache + audit log    │  │
                                    │  │    risk-adaptive TTL    │  │
                                    │  └────────┬────────────────┘  │
                                    │           ▼                   │
                                    │      response JSON            │
                                    └──────────────────────────────┘
```

## Why "Hybrid"? / 为什么是混合架构？

**Failure mode of pure ML**: feed Mt Everest coordinates → trained on tropical Malaysian mountains → predicts ~0 % rain → ignores -30 °C, 80 km/h winds, 8800 m hypoxia → returns "Safe". A hiker dies.

**Mitigation**: the Rule Engine is the **safety net**. It encodes physical / medical thresholds that are *true everywhere*, not learned from data. ML provides nuanced in-distribution probability; rules provide bounded out-of-distribution guarantees.

This split — learnable component + symbolic component — is the **Neuro-Symbolic AI** paradigm (Garcez & Lamb, 2020).

## Module responsibilities

| Module | Responsibility |
|---|---|
| `backend/main.py` | FastAPI app + lifespan (model load, DB init, HTTP client) |
| `backend/ml_engine.py` | Load joblib RF, run `predict_proba`; heuristic fallback when no model artefact |
| `backend/rule_engine.py` | Veto cascade + additive scoring + bilingual advice + XAI log |
| `backend/terrain.py` | 3×3 DEM fetch, slope/aspect/TPI, orographic-uplift dot product |
| `backend/cache.py` | WAL-SQLite grid cache, risk-adaptive TTL, inference audit log |
| `backend/config.py` | Single source of truth for thresholds + academic citations |
| `backend/schemas.py` | Pydantic v2 request/response contract |
| `scripts/1_download_dataset.py` | Open-Meteo + Open-Topo-Data ingestion (5 Malaysian sites, 5 years) |
| `scripts/2_preprocess.py` | Feature engineering + `is_rain_event` label derivation |
| `scripts/3_train_model.py` | Random Forest + time-based CV + classification report + feature importance |
| `frontend/index.html` | Single-file Vue3 SPA: Leaflet map, gauge, XAI log, EN/ZH toggle |

## Concurrency model

* FastAPI is single-event-loop async. All blocking I/O (SQLite) is wrapped in `asyncio.to_thread` so it never stalls the loop.
* SQLite is opened in **WAL** mode (`PRAGMA journal_mode=WAL`) so readers don't block on writers.
* `httpx.AsyncClient` is shared across the app via `app.state.http`, instantiated in lifespan.
* External calls use exponential-backoff retries (`tenacity`) and 15 s timeouts.

## Cache strategy

A naive fixed TTL is unsafe — a 10-minute-stale "Safe" verdict during a developing storm can kill someone. We use **risk-adaptive TTL**:

| Risk score / Veto | TTL |
|---|---|
| Any Veto fired, or score ≥ 70 | **60 s** |
| Score 40-70 | 300 s |
| Score < 40 | 600 s |

Grid key quantises (lat, lon) to ~1.1 km cells (`GRID_RESOLUTION_DEG = 0.01`).
