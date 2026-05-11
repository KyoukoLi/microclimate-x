# Model Card — MicroClimate-X Rain Predictor (Random Forest v1.0)

> Following the *Model Card* methodology of Mitchell et al. (2019).
> Authored: 2026-05-11 · UKM Final Year Project · KyoukoLi

---

## 1. Model Details

| Field | Value |
|---|---|
| **Model name** | MicroClimate-X RF Rain Predictor |
| **Version** | 1.0.0 |
| **Architecture** | `sklearn.ensemble.RandomForestClassifier` |
| **Hyper-parameters** | `n_estimators=200, max_depth=None, class_weight='balanced', n_jobs=-1, random_state=42` |
| **Features (n=18)** | `elevation_m`, `temperature_c`, `humidity_pct`, `wind_speed_kmh`, `wind_direction_deg`, `pressure_hpa`, `dew_point_c`, `cloud_cover_pct`, `cape_jkg`, `visibility_m`, `wind_u`, `wind_v`, `hour_sin`, `hour_cos`, `month_sin`, `month_cos`, `dew_point_depression`, `pressure_change_3h`, `precipitation_lag_1h` |
| **Target** | `is_rain_event` ∈ {0, 1} — defined as `precipitation(t+1h) > 0.1 mm` |
| **Output** | `predict_proba(...)[:, 1]` — calibrated probability of rain in the next hour |
| **Author / Contact** | Li Zhenyue (`KyoukoLi`), Faculty of Information Science & Technology, UKM |
| **Licence** | MIT (see `LICENSE`) |

---

## 2. Intended Use

* **Primary use case**: terrain-aware rain-risk decision support inside the MicroClimate-X *hybrid* pipeline. The RF probability is one input among many — the topographic Rule Engine has *final authority* (Veto cascade + R1-R4 decision table).
* **Intended users**: hikers, drivers, construction crews, and other outdoor decision makers in complex terrain (initially Malaysian mountain regions).
* **Out-of-scope uses**:
  * Lightning forecasting (CAPE → thunderstorm risk is handled by the rule engine sub-scorer, not by this model).
  * Multi-hour quantitative precipitation forecasting.
  * Aviation, marine, or any life-critical use without the Rule Engine veto layer in the loop.

---

## 3. Training Data

| Field | Value |
|---|---|
| **Source** | ECMWF ERA5 Reanalysis (via Open-Meteo Historical Archive API) |
| **Spatial coverage** | 5 mountain sites in West Malaysia (Genting, Cameron, Brinchang, Korbu, Kinabalu) |
| **Temporal coverage** | 2019-01-01 → 2024-12-31 (5 years, hourly) |
| **Total rows** | 175 315 |
| **Class balance** | 29.2 % positive (rain-event), 70.8 % negative |
| **Train / test split** | Time-based; 80 % oldest → train; 20 % newest → test. **No random shuffling** — would leak temporal autocorrelation. |
| **Synthetic fallback** | `scripts/1b_synth_dataset.py` generates a physically-plausible synthetic replacement when the Open-Meteo API is unreachable. The synthetic data set has the same schema and is sufficient for end-to-end pipeline verification but should **not** be used to ship a production model. |

---

## 4. Evaluation — Held-out 20 % temporal test set (n = 35 063)

Numbers below come from `figures/evaluation_summary.json`, reproducible via `make evaluate`.

### 4.1 Discrimination

| Metric | Value |
|---|---|
| ROC AUC | **0.871** |
| PR Average Precision | **0.750** |
| Test-set base rate | 0.292 |

### 4.2 Calibration

| Metric | Value |
|---|---|
| Brier score | **0.138** (lower is better; 0 is perfect, 0.25 is random) |

The reliability diagram (`figures/03_calibration_curve.png`) shows the predicted probability tracks the empirical frequency closely; no post-hoc calibration (Platt / isotonic) was deemed necessary.

### 4.3 Operating point — safety-critical threshold

| Threshold τ | F1 | F2 | Precision | Recall |
|---|---|---|---|---|
| 0.50 (default) | 0.696 | 0.694 | 0.700 | 0.692 |
| **0.20 (chosen)** | 0.621 | **0.778** | 0.466 | **0.934** |

We adopt **τ = 0.20** because the application is **safety-critical**: a missed rain event (false negative) on a windward slope can cascade into orographic flash flooding. F2 weights recall 4× higher than precision and is the appropriate metric for this regime (Sasaki, 2007).

### 4.4 Confusion matrix at τ = 0.20

|              | Pred = 0 | Pred = 1 |
|---|---|---|
| **True = 0** | 13 877 (TN) | 10 950 (FP) |
| **True = 1** | 679 (FN)    | 9 557 (TP) |

Recall = 9 557 / (9 557 + 679) = **93.4 %** — the operationally important metric for "do not let people walk into a storm".

### 4.5 Top feature importances

1. `precipitation_lag_1h` — recent rain is by far the strongest signal (rain begets rain).
2. `hour_cos` / `hour_sin` — diurnal cycle (afternoon convective storms in tropical climates).
3. `pressure_change_3h` — falling pressure is a classical storm precursor.
4. `wind_v` — meridional wind component, relevant for monsoon-driven precipitation.
5. `dew_point_c` / `dew_point_depression` / `temperature_c` — moisture saturation indicators.

---

## 5. Quantitative Limitations

* **Geographic generalisation** — the model has only seen West Malaysian mountains. Hindcast validation in other tropical mountainous regions is a planned thesis Chapter 5 contribution; until then, the Rule Engine Veto cascade is the only safety net for out-of-distribution coordinates (e.g. Himalayas).
* **Convective forecasting** — the model uses *current-hour* features to predict *next-hour* rain. Forecasting horizon > 1 h would degrade accuracy substantially.
* **Class imbalance** — addressed via `class_weight='balanced'` and the F2-optimal threshold, but precision at τ = 0.20 is moderate (47 %). False positives are tolerable because they only inflate the *rainfall sub-score*; the composite-score formula combines this with three other hazards.
* **Calibration drift** — Brier = 0.138 in 2024 hold-out. Calibration should be re-checked annually as climate signals shift.

---

## 6. Ethical / Safety Considerations

* **Decision-support only.** The system is explicitly **not** a substitute for official meteorological forecasts; the disclaimer is shown in every UI footer.
* **Hidden risk surfaced, not hidden.** The R1 decision-table rule deliberately raises an alarm when *macro* model probability is low but local terrain inputs suggest hidden orographic rain — this is the OPPOSITE of the harmful failure mode where ML over-confidently says "safe".
* **Mt-Everest test (worst-case OOD).** When fed coordinates the model has never seen, the RF returns ~0 % rain probability — and the Rule Engine then immediately vetoes on `altitude_hypoxia + extreme_cold + gale_wind`. See `tests/test_rule_engine.py::test_mt_everest_veto_hypoxia`.

---

## 7. Reproducibility

```bash
# Full pipeline from scratch — works offline via the synthetic dataset.
make install-dev
make synth          # OR: download real data via scripts/1_download_dataset.py
make preprocess
make train
make evaluate       # writes figures/*.png + figures/evaluation_summary.json
```

The seed is fixed (`random_state=42`) and figures are written to `figures/` so the thesis can pull them in directly.

---

## 8. Citation

If you reference this model in academic work, please cite:

> Li Zhenyue (KyoukoLi). *MicroClimate-X: A Hybrid Microclimate Risk Engine for Complex Terrain*. Bachelor's Thesis, Universiti Kebangsaan Malaysia, Faculty of Information Science & Technology, 2026. GitHub: <https://github.com/KyoukoLi/microclimate-x>
