# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-05-11

The first complete release. Engineering-grade hardening across backend,
ML pipeline, frontend, and DevOps; the rule engine is fully aligned with
the D5 thesis proposal §3.7 / P4.

### Added — Backend

- **Request-ID middleware** that stamps every response with `X-Request-ID`
  and `X-Response-Time-ms`. Incoming `X-Request-ID` headers propagate end
  to end, enabling cross-service tracing.
- **Centralised error contract** (`backend/errors.py`) — every non-2xx
  response is a typed `ErrorResponse { error, detail, request_id, context }`
  JSON document; no bare 500-HTML responses leak.
- **Structured logging** with per-request log records (`request_id` field
  on every line, ISO-8601 timestamps).
- **Enriched `/api/health`** reporting uptime, cache row counts (live /
  expired / total), DB size, and inference-log size.
- **`/api/version`** endpoint returning version + git short SHA + ML
  feature schema.
- **Cache hygiene** — `prune_expired()` runs on startup, sweeps inference-log
  rows older than 7 days, and `cache_stats()` is exposed via `/api/health`.
- **Fire-and-forget cache writes** with the task reference retained
  (`asyncio.create_task` lint compliance).
- **Defensive ML engine** — `predict_rain_probability` always returns
  `float ∈ [0, 1]`; NaN/Inf/wrong-type feature values gracefully degrade;
  model-load failures fall through to the heuristic instead of crashing.
- **Improved heuristic fallback** — now also responds to
  `pressure_change_3h` so the "no model yet" demo still behaves sensibly.
- **Terrain edge cases** — antimeridian wrap, polar clamp, ocean / no-data
  DEM cells handled instead of raising obscure type errors.

### Added — Rule Engine (already shipped, now fully tested)

- 4 sub-hazard scorers — rainfall / fog / wind gust / thunderstorm.
- D5 §3.7.2 R1-R4 Decision Table.
- Activity-aware weighted composite (`hiker | driver | construction | general`).
- Dominant-hazard composite formula: `0.80·max + 0.20·mean(rest)`.

### Added — ML pipeline

- **`scripts/4_evaluate_model.py`** generating publication-quality figures
  (ROC + AUC, PR + AP, calibration / Brier, threshold sweep, top-20
  feature importance, confusion matrix at F2-optimal threshold).
- **`figures/evaluation_summary.json`** machine-readable evaluation blob
  for the thesis appendix.
- **`figures/threshold_sweep.csv`** for full reproducibility of the
  precision-recall trade-off table.
- **`models/MODEL_CARD.md`** — HuggingFace-style model card with intended
  use, training data, evaluation, limitations, and ethical considerations.

### Added — Tests

- HTTP integration tests with `respx`-mocked external APIs
  (`tests/test_api.py`): happy path, cache hit, distinct cache slot per
  activity, invalid input → 422, upstream failure → 502, CORS, OpenAPI
  schema.
- Cache layer tests (`tests/test_cache.py`): TTL, expiry, prune, stats.
- Terrain edge-case tests (`tests/test_terrain_edge.py`): antimeridian,
  polar clamp, malformed DEM.
- ML engine tests (`tests/test_ml_engine.py`): unloaded behaviour,
  heuristic monotonicity, NaN/None resilience.
- Session-scoped `conftest.py` sets an isolated `MICROCLIMATEX_DB` for
  every test run (no clobbering the dev cache).
- **Total: 70 tests; backend coverage 97 %.**

### Added — Frontend

- Activity selector (Hiker / Driver / Construction / General) with
  `localStorage` persistence and keyboard accessibility (`aria-pressed`
  + `focus-visible`).
- 4 mini-gauges for the per-hazard sub-scores, each with a tooltip
  explaining what drives it.
- D5 §3.7.2 R1-R4 indicator badges (highlight when fired).
- Demo scenarios dropdown (Genting · Cameron · Kinabalu · Everest · Singapore).
- **Loading spinner** during in-flight requests.
- **Toast notification** for errors and "no model loaded" warnings.
- **Map layer switcher** — Dark base + Topographic option.
- Bilingual EN/ZH UI persisted across reloads.

### Added — DevOps / Reproducibility

- **GitHub Actions CI** (`.github/workflows/ci.yml`) — pytest matrix on
  Python 3.9 / 3.11 / 3.12, ruff lint, coverage XML artefact, plus a
  Docker image-build smoke test with Buildx + GHA cache.
- **Multi-stage Dockerfile** — builder stage for wheels, slim runtime
  with a non-root `mcx` user, baked-in HEALTHCHECK against `/api/health`.
- **`docker-compose.yml`** with a named data volume.
- **`Makefile`** — single-word recipes for `install`, `test`, `lint`,
  `run`, `synth`, `preprocess`, `train`, `evaluate`, `docker`, `clean`.
- **`requirements-dev.txt`** — split dev tooling (pytest-cov, ruff,
  respx, matplotlib) from runtime requirements.
- **`pyproject.toml`** — ruff configuration + pytest config.
- **`.pre-commit-config.yaml`** — trailing-whitespace, end-of-file,
  YAML/JSON/TOML checks, large-file guard, ruff lint + format.
- **`.dockerignore`** keeping the image lean.

### Added — Documentation

- `docs/architecture.md` — P4.1 → P4.6 internal flow + dominant-hazard
  formula rationale.
- `docs/thresholds.md` — every threshold cited; new §8-§12 for the four
  hazard categories, R1-R4 table, and activity-weight matrix.
- `docs/dataset.md` — formal target definition (`is_rain_event`) and
  train/test split rationale.

### Changed

- Rainfall sub-scorer calibration — 45 % macro probability now lands at
  ~ 40 (Caution band), matching the proposal's intent.
- Composite-score formula switched from naive arithmetic mean to
  **dominant-hazard + secondary** to avoid mean dilution.
- Cache key now incorporates `activity` — different weights → different
  composite → must not share a slot.

### Fixed

- `tenacity.RetryError` from the retry decorator was not caught by the
  `except httpx.HTTPError` clause, producing a misleading 500. Now caught
  alongside `httpx.HTTPError` and `ValueError`, returning a clean 502.

---

## [0.2.0] — 2026-05-11

Initial D5-alignment pass — see commit `55fd759`.

## [0.1.0] — 2026-05-11

Project scaffolding and Hybrid Engine v1 — see commits `b218f5b`
through `4639890`.
