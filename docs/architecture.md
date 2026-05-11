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
                                    │  │  ┌───────────────────┐  │  │
                                    │  │  │ P4.3 four hazard  │  │  │
                                    │  │  │  sub-scorers      │  │  │
                                    │  │  └─────────┬─────────┘  │  │
                                    │  │  ┌───────────────────┐  │  │
                                    │  │  │ §3.7.2 decision   │  │  │
                                    │  │  │  table R1-R4      │  │  │
                                    │  │  └─────────┬─────────┘  │  │
                                    │  │  ┌───────────────────┐  │  │
                                    │  │  │ Veto cascade      │  │  │
                                    │  │  └─────────┬─────────┘  │  │
                                    │  │  ┌───────────────────┐  │  │
                                    │  │  │ P4.4 activity-    │  │  │
                                    │  │  │  weighted composite│ │  │
                                    │  │  └─────────┬─────────┘  │  │
                                    │  │    Bilingual advice    │  │
                                    │  └────────┬───────────────┘  │
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

## Engine B internals (D5 proposal §3.7 — P4)

Engine B is structured in **one-to-one correspondence** with sub-process §3.7 of the proposal so the thesis chapter can quote line numbers directly:

| Proposal section | Code artefact | What it does |
|---|---|---|
| **P4.1** Load Dynamic Risk Rules | `backend/config.py` — `DECISION_TABLE_3_7_2`, `ACTIVITY_WEIGHTS`, all `PENALTY_*` / threshold constants | Single source of truth for every threshold, weight, and rule, each annotated with the citation it is derived from. |
| **P4.2** Fetch User Context | `?activity={hiker,driver,construction,general}` query parameter, plumbed to `evaluate(activity=…)` | Captures who the user is so weights can be applied later. |
| **P4.3** Evaluate Environmental Risks | Four `score_*_risk()` functions in `rule_engine.py`: rainfall, fog, wind gust, thunderstorm | Each returns a 0-100 sub-score using ML probability + weather + terrain inputs. |
| **§3.7.2 Table 4.2** Decision Table | `apply_decision_table_3_7_2()` | Returns which of R1-R4 fire (hidden rain on windward slope; no amplification on leeward; heavy downpour incoming; normal rain). Emits an `[table]` line in the XAI log per match. |
| **Veto cascade** | `_collect_veto_triggers()` | Life-safety overrides (altitude hypoxia, extreme cold, gale wind, high CAPE, low visibility, valley flash-flood, orographic-lift storm). When any fires, composite is capped at 100 and a `Danger` verdict is returned regardless of ML probability. |
| **P4.4** Activity-Specific Weighting | `apply_activity_weighting()` + `ACTIVITY_WEIGHTS` matrix | Weights per (activity × hazard) pair (e.g. driver weights fog 1.5×, construction weights wind 1.5×). |
| **P4.5** Composite Risk Score | Same function | Composite = 0.80 · max(weighted sub-scores) + 0.20 · mean(rest). Dominant hazard wins; secondary hazards lift the score modestly. |
| **P4.6** Actionable Advice | `_normal_advice()` / `_veto_advice()` | Bilingual EN/ZH narrative mentioning the dominant hazard, the terrain, and the activity. |

### Why "dominant-hazard composite" instead of a plain weighted sum?

A naive arithmetic mean dilutes the dominant hazard — a thunderstorm sub-score of 90 averaged with three sub-scores of 10 would yield only 30, which understates real danger. The dominant-hazard formula gives the **single worst hazard for that user** 80 % of the weight; the remaining 20 % captures the compounding effect when multiple hazards are simultaneously elevated. Per-hazard scores are clipped to 100 before aggregation so a weight > 1 cannot push a single sub-score past saturation.


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
