# MicroClimate-X

> Intelligent Meteorological Analysis System for Complex Terrain  
> 面向复杂地形的智能气象分析系统

![CI](https://github.com/KyoukoLi/microclimate-x/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.9%20%7C%203.11%20%7C%203.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688)
![Vue3](https://img.shields.io/badge/Vue.js-3-4FC08D)
![ML](https://img.shields.io/badge/ML-RandomForest-orange)
![Coverage](https://img.shields.io/badge/coverage-97%25-brightgreen)
![Tests](https://img.shields.io/badge/tests-70%20passing-success)
![Docker](https://img.shields.io/badge/Docker-multi--stage-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

A Final Year Project at **Universiti Kebangsaan Malaysia (UKM)** — Faculty of Information Science & Technology.

---

## 1. Problem Statement / 痛点

Traditional weather forecasting relies on **macro-scale grids (20 km × 20 km)** that fail catastrophically in complex terrain. A single forecast cell may cover a mountain peak, a valley floor, and a windward slope — all of which have vastly different microclimates.

传统天气预报使用 **20 km × 20 km 宏观网格**，在山区会严重失真。同一网格内可能同时包含山顶、谷底和迎风坡，但它们的微气候完全不同。

## 2. Solution: The Hybrid Engine / 解决方案

MicroClimate-X uses a **dual-engine hybrid architecture** combining a Machine Learning predictor with a topographic Rule-Based Expert System.

```
            ┌──────────────────────────────────────────────────┐
            │  User clicks a coordinate on the map (lat, lon)  │
            └────────────────────┬─────────────────────────────┘
                                 │
            ┌────────────────────▼─────────────────────────────┐
            │   Open-Meteo (weather) + Open Topo Data (DEM)    │
            └────────────────────┬─────────────────────────────┘
                                 │
              ┌──────────────────┴───────────────────┐
              │                                      │
   ┌──────────▼──────────┐              ┌────────────▼───────────┐
   │  Engine A           │              │  Engine B              │
   │  Random Forest      │   probability│  Topographic Rules     │
   │  (in-distribution   ├─────────────►│  + Veto Triggers       │
   │   rain probability) │              │  (safety-critical)     │
   └─────────────────────┘              └────────────┬───────────┘
                                                     │
                                        ┌────────────▼───────────┐
                                        │  Risk Score 0-100      │
                                        │  + Bilingual Advice    │
                                        │  + XAI Inference Log   │
                                        └────────────────────────┘
```

### Why Hybrid? / 为什么混合？

Pure ML can fail catastrophically out-of-distribution. Example: feed Mount Everest coordinates → ML predicts 0% rain → returns "Safe" — ignoring -30°C, hypoxia, gale-force winds.

**Engine B's Veto mechanism** provides bounded safety guarantees by overriding the ML score when physical thresholds are breached. This follows the **Neuro-Symbolic AI** paradigm (Garcez & Lamb, 2020).

### Engine B internals — one-to-one with D5 proposal §3.7 / P4

The rule engine is decomposed exactly along the lines of the thesis proposal so every line of code maps to a section number:

| Proposal step | Code | Output |
|---|---|---|
| **P4.1** Load Dynamic Risk Rules | `backend/config.py` | All thresholds, weights, and the R1-R4 decision table, each annotated with its academic citation |
| **P4.2** Fetch User Context | `?activity=hiker\|driver\|construction\|general` | Activity is plumbed into the request flow |
| **P4.3** Evaluate Environmental Risks | Four `score_*_risk()` functions in `rule_engine.py` | Rainfall / Fog / Wind-gust / Thunderstorm sub-scores (each 0-100) |
| **§3.7.2 Table 4.2** Decision Table | `apply_decision_table_3_7_2()` | Which of R1-R4 fired (hidden rain / no amplification / heavy downpour / standard rain) |
| Veto cascade | `_collect_veto_triggers()` | Life-safety overrides (Mt-Everest type) — capped at 100 |
| **P4.4** Activity weighting | `apply_activity_weighting()` | (activity × hazard) weight matrix |
| **P4.5** Composite score | Same | `0.80 · max(weighted) + 0.20 · mean(rest)` — dominant hazard wins |
| **P4.6** Actionable advice | `_normal_advice()` / `_veto_advice()` | Bilingual EN/ZH paragraph that names the dominant hazard |

Four hazard categories surfaced in the UI as four mini-gauges; the four R1-R4 indicators light up beside the score card whenever a rule fires.

## 3. Tech Stack / 技术栈

| Layer | Technology |
|---|---|
| Frontend | Vue 3 (CDN) + Tailwind CSS + Leaflet.js + ECharts |
| Backend | Python 3.10+, FastAPI, Uvicorn |
| ML | Scikit-Learn (Random Forest), Pandas, NumPy |
| Storage | SQLite 3 (WAL mode, risk-adaptive TTL cache) |
| External | Open-Meteo Historical Archive (ERA5), Open Topo Data (SRTM DEM) |

## 4. Dataset / 数据集

- **Source**: [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) (ERA5 reanalysis)
- **Region**: Malaysian mountain areas (Genting Highlands, Cameron Highlands, Fraser's Hill, Klang Valley, Mount Kinabalu region)
- **Time Range**: 2020-01-01 to 2023-12-31 (hourly resolution, 5 sites × ~35 000 hours each)
- **Features (X)**: `elevation_m`, `temperature_c`, `humidity_pct`, `wind_speed_kmh`, `wind_direction_deg`, `surface_pressure_hpa`
- **Target (Y)**: `is_rain_event` — binary, 1 if `precipitation(t+1h) > 0.1 mm` else 0 (per WMO trace-precipitation definition)

## 5. Quick Start / 快速开始

```bash
git clone https://github.com/KyoukoLi/microclimate-x.git
cd microclimate-x

# Fast path — everything via the Makefile
make install-dev         # 1. create venv + install runtime + dev deps
make synth               # 2. generate synthetic dataset (offline)
#  …or `make` nothing here and run `python scripts/1_download_dataset.py`
#     to fetch real ERA5 data when network is available.
make preprocess          # 3. feature engineering + Y derivation
make train               # 4. RF training + time-based CV
make evaluate            # 5. ROC / PR / calibration / threshold-sweep figures
make run                 # 6. uvicorn dev server on http://localhost:8000

# Then open frontend/index.html (or browse to http://localhost:8000/app/)
```

### Docker one-liner

```bash
docker compose up --build
# API lives on http://localhost:8000  ·  frontend on http://localhost:8000/app/
```

### Test it

```bash
make test         # 70 tests, ~12 s
make lint         # ruff — zero errors expected
```

### Training results on real ERA5 data / 真实 ERA5 数据训练结果

Trained on **175 315 hourly samples** from Open-Meteo Historical Archive
(ECMWF ERA5 reanalysis) covering five Malaysian mountain sites,
2020-01-01 → 2024-12-31. Time-based split: last 20 % per site held out
(n = 35 063 test samples). See [`models/MODEL_CARD.md`](models/MODEL_CARD.md)
for the full evaluation card and `figures/` for publication-ready plots.

| Metric | Value | Source |
|---|---|---|
| Test ROC AUC | **0.871** | `figures/01_roc_curve.png` |
| Test PR Average Precision | **0.750** | `figures/02_pr_curve.png` |
| Brier score (calibration) | **0.138** | `figures/03_calibration_curve.png` |
| Best F2 @ τ = 0.20 | **0.778** | `figures/04_threshold_sweep.png` |
| Recall (at chosen τ = 0.20) | **0.934** — safety-critical recall |
| Class balance | 29.2 % positive (Malaysian mountain climatology) |

We deliberately operate at **τ = 0.20**, not the default 0.50, because
in safety-critical settings a missed rain event (false negative) on a
windward slope is dramatically worse than a false positive. F2 score
weights recall 4× higher than precision and is the principled metric
for this regime.

**5-fold time-series CV** on the training fold gives AUC ranging
0.828-0.908 (mean ≈ 0.858), confirming the model is not over-fitting a
single temporal slice.

#### Feature importance — what the model actually learned

| Rank | Feature | Importance | Interpretation |
|---|---|---|---|
| 1 | `precipitation_lag_1h` | 37.1 % | Rain autocorrelation — the well-documented "rain begets rain" persistence signal in short-term nowcasting (Wilson et al., 2010). |
| 2-3 | `hour_cos`, `hour_sin` | 18.6 % | Diurnal convective cycle — Malaysian mountain rainfall peaks in late afternoon. |
| 4 | `pressure_change_3h` | 4.7 % | Falling pressure precedes incoming storms — the classical synoptic-scale precursor. |
| 5-6 | `wind_v`, `dew_point_c` | 8.1 % | Moisture transport + saturation potential. |
| 7-14 | other meteorological X | 22 % | T, humidity, cloud cover, wind, dew-point depression, pressure. |
| 15-17 | `month_*`, `elevation_m` | 4 % | Low because the time-of-day and lag features already absorb most of the seasonal/static signal. |
| 18 | `cape_jkg` | **0.0 %** | ⚠️ ERA5 archive CAPE values for these coordinates are predominantly zero — a known coverage gap. The Veto-rule engine still uses CAPE thresholds directly from the live Open-Meteo forecast at inference time. |

#### Why F2 instead of accuracy?

Accuracy is misleading on imbalanced safety-critical classification.
A model that predicts "no rain" 100 % of the time achieves
**69.2 % accuracy** here while being completely useless. F2 weights
recall twice as heavily as precision, which is correct for a
hiker-safety app where missing a real rain event (False Negative) is
far worse than a false alarm (False Positive).

See `models/training_report.json` for the full 5-fold CV report.

## 6. Project Structure / 项目结构

```
microclimate-x/
├── backend/
│   ├── main.py           # FastAPI app + lifespan
│   ├── ml_engine.py      # Loads RF model, predict_proba
│   ├── rule_engine.py    # Veto rules + risk scoring + bilingual advice
│   ├── terrain.py        # DEM-based Valley/Slope/Flat classification
│   ├── cache.py          # SQLite WAL cache, risk-adaptive TTL
│   ├── schemas.py        # Pydantic request/response models
│   └── config.py         # Thresholds + academic citations
├── scripts/
│   ├── 1_download_dataset.py    # Open-Meteo + Open-Topo-Data (real ERA5)
│   ├── 1b_synth_dataset.py      # physically-plausible offline fallback
│   ├── 2_preprocess.py
│   └── 3_train_model.py
├── frontend/
│   └── index.html        # Single-file Vue3 SPA
├── docs/
│   ├── architecture.md
│   └── thresholds.md     # Veto thresholds with academic citations
├── tests/
│   └── test_rule_engine.py
├── data/                 # raw/processed CSVs (gitignored)
├── models/               # trained .pkl artifacts (gitignored)
└── requirements.txt
```

## 7. Key Design Decisions / 关键设计

| Decision | Rationale |
|---|---|
| **Random Forest over SVM / Deep Learning** | Handles non-linear weather-terrain interactions; outputs interpretable feature importance; no GPU needed; robust on tabular data |
| **Binary classification (`is_rain_event`)** | One-hour-ahead nowcasting matches the use case (hikers' immediate decisions) |
| **Time-based train/test split** | Random split would leak temporal correlation → inflated metrics |
| **Class-weight balanced** | Rain is the minority class (~25% in Malaysian mountains) |
| **Wind direction as u/v components** | Raw degrees treat 0° and 360° as far apart — mathematically incorrect |
| **Risk-adaptive cache TTL** | High-risk scenarios refresh faster (60 s) than safe ones (600 s) |
| **SQLite WAL mode** | Allows concurrent reads during writes — critical for FastAPI async |

## 8. Academic References / 学术参考

1. **Bhuiyan, M. A. E., et al.** (2020). *Improving satellite-based precipitation estimates over complex terrain using machine learning algorithms*. **Journal of Hydrology**.
2. **Maclean, I. M., et al.** (2018). *Microclima: An R package for modelling meso- and microclimate*. **Methods in Ecology and Evolution**.
3. **Garcez, A. d., & Lamb, L. C.** (2020). *Neurosymbolic AI: The 3rd Wave*. arXiv:2012.05876.
4. **Luks, A. M., et al.** (2019). *Wilderness Medical Society Practice Guidelines for the Prevention and Treatment of Acute Altitude Illness*.
5. **Vandal, T., et al.** (2017). *DeepSD: Generating high-resolution climate change projections through single image super-resolution*. **KDD**.

See `docs/thresholds.md` for the full citation table per Veto threshold.

## 9. Roadmap

- [x] Frontend dashboard with XAI inference log
- [x] SQLite caching with WAL + risk-adaptive TTL
- [x] Terrain detection engine (Valley / Slope / Flat)
- [x] Rule-based Veto + 0-100 scoring engine (19/19 unit tests passing)
- [x] Bilingual (EN/ZH) advice generation
- [x] Dataset download script (Open-Meteo + Open Topo Data) + offline synthetic fallback
- [x] Preprocessing pipeline (feature engineering + label `is_rain_event`)
- [x] Random Forest training with time-based CV — **trained on real ERA5 data, test AUC = 0.871**
- [ ] Model comparison (RFC vs LogReg vs XGBoost) — thesis Chapter 5
- [ ] Hindcast validation against real Malaysian flood events
- [ ] PWA offline mode for low-network mountain use

## 10. License

MIT — see `LICENSE`.

---

*Developed by L.ZH @ Universiti Kebangsaan Malaysia (UKM) for the Final Year Project (FYP).*
