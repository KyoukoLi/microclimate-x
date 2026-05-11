# MicroClimate-X

> Intelligent Meteorological Analysis System for Complex Terrain  
> 面向复杂地形的智能气象分析系统

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688)
![Vue3](https://img.shields.io/badge/Vue.js-3-4FC08D)
![ML](https://img.shields.io/badge/ML-RandomForest-orange)
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
# 1. Clone & install
git clone https://github.com/KyoukoLi/microclimate-x.git
cd microclimate-x
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2a. (Recommended) Download real ERA5 data via Open-Meteo (~5-10 min)
python scripts/1_download_dataset.py
#  …or 2b. Offline fallback — generate a physically-plausible synthetic
#         dataset with the same schema (~2 seconds, no network needed)
python scripts/1b_synth_dataset.py

# 3. Preprocess + engineer features + label Y
python scripts/2_preprocess.py

# 4. Train Random Forest (time-based split + classification report)
python scripts/3_train_model.py

# 5. Launch API
uvicorn backend.main:app --reload --port 8000

# 6. Open frontend
open frontend/index.html   # macOS
# or just double-click frontend/index.html
```

### Training results on real ERA5 data / 真实 ERA5 数据训练结果

Trained on **175 315 hourly samples** from Open-Meteo Historical Archive
(ECMWF ERA5 reanalysis) covering five Malaysian mountain sites,
2020-01-01 → 2023-12-31. Time-based split: last 20 % per site held out.

| Metric | Value |
|---|---|
| Test AUC      | **0.871** |
| Test F1 (rain) | 0.686 |
| Test F2 (rain) | **0.724** (we prefer F2 — recall matters more for safety) |
| Recall (rain)  | 0.751 |
| Precision (rain) | 0.631 |
| Class balance  | 30.8 % positive (matches Malaysian mountain climatology) |

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
