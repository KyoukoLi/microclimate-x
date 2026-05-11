# Dataset Specification
# 数据集说明

> The exact dataset structure that the supervisor approved at the 4/15 review.
> 4 月 15 日导师 review 后确认的数据集结构。

## 1. Source / 数据来源

| Component | Source | URL |
|---|---|---|
| Hourly weather | Open-Meteo Historical Weather API (ECMWF ERA5 reanalysis) | https://open-meteo.com/en/docs/historical-weather-api |
| Elevation     | Open-Topo-Data (SRTM 30 m DEM) | https://www.opentopodata.org/datasets/srtm/ |

ERA5 is the gold-standard reanalysis dataset in academic meteorology, providing physically-consistent hourly values from 1940 to present.

## 2. Spatial coverage / 空间覆盖

Five Malaysian mountain locations, chosen to span a range of elevations and terrain types:

| Site | Latitude | Longitude | Approx. elev. | Terrain |
|---|---|---|---|---|
| Genting Highlands  | 3.4225 | 101.7935 | ~1865 m | Slope |
| Cameron Highlands  | 4.4694 | 101.3776 | ~1500 m | Highland plateau |
| Fraser's Hill      | 3.7256 | 101.7378 | ~1300 m | Slope |
| Klang Valley       | 3.0738 | 101.5183 |  ~100 m | Valley floor |
| Mt Kinabalu (base) | 6.0535 | 116.5586 | ~1800 m | Mountain |

## 3. Temporal coverage / 时间范围

**2020-01-01 → 2023-12-31**, hourly resolution (one row per hour per site).

Expected sample count: 5 sites × 4 years × 365.25 days × 24 hours ≈ **175 320 rows**.

## 4. Schema / 列结构

| Position | Column | Type | Role | Description |
|---|---|---|---|---|
| 0 | `site`               | str   | meta    | Site name |
| 1 | `latitude`           | float | meta    | WGS84 |
| 2 | `longitude`          | float | meta    | WGS84 |
| 3 | `elevation_m`        | float | **X**   | DEM-derived altitude (static per site) |
| 4 | `time`               | datetime | meta | Hourly UTC+8 (Asia/Kuala_Lumpur) |
| 5 | `temperature_c`      | float | **X**   | 2 m air temperature |
| 6 | `humidity_pct`       | float | **X**   | Relative humidity 0-100 |
| 7 | `precipitation`      | float | (raw)   | mm in past hour — used to derive Y |
| 8 | `wind_speed_kmh`     | float | **X**   | 10 m wind speed |
| 9 | `wind_direction_deg` | float | **X**   | Direction FROM which wind blows, 0-360° |
| 10 | `wind_u`            | float | **X**   | u = speed · sin(dir) |
| 11 | `wind_v`            | float | **X**   | v = speed · cos(dir) |
| 12 | `pressure_hpa`      | float | **X**   | Surface pressure |
| 13 | `pressure_change_3h`| float | **X**   | Δp over preceding 3 h (storm precursor) |
| 14 | `dew_point_c`       | float | **X**   | 2 m dew-point |
| 15 | `dew_point_depression` | float | **X** | T − T_dew (saturation proxy) |
| 16 | `cloud_cover_pct`   | float | **X**   | Total cloud cover 0-100 |
| 17 | `cape_jkg`          | float | **X**   | Convective Available Potential Energy |
| 18 | `precipitation_lag_1h` | float | **X** | Previous hour's precipitation |
| 19 | `hour_sin`, `hour_cos` | float | **X** | Cyclic encoding of hour-of-day |
| 20 | `month_sin`, `month_cos` | float | **X** | Cyclic encoding of month (captures monsoon) |
| 21 | **`is_rain_event`** | **int {0,1}** | **Y** | **1 if `precipitation(t+1h) > 0.1 mm` else 0** |

## 5. Target label derivation / 目标标签的衍生

This is **THE** column that earlier supervisor feedback flagged as missing in the raw CSV. It is engineered explicitly in `scripts/2_preprocess.py`:

```python
df['is_rain_event'] = (df['precipitation'].shift(-1) > 0.1).astype(int)
```

Three things the panel should notice:

1. **`.shift(-1)` means future**: features at time `t` are paired with the rain outcome at `t+1h`. The model never sees future data as input — this prevents temporal data leakage.
2. **0.1 mm threshold**: this matches the **WMO definition of trace precipitation** — i.e. it is *not* an arbitrary cutoff.
3. **Binary**, not amount-of-rain. The pipeline could be extended to a regression task; we deliberately model classification because the downstream user decision is binary ("go / no-go").

## 6. Train / test split / 划分策略

**Time-based**, not random. The last 20 % of each site's chronological data is reserved as the hold-out test set; the remaining 80 % goes to a 5-fold `TimeSeriesSplit` cross-validation. Random splits would leak temporal autocorrelation and inflate accuracy by 5-15 percentage points.

## 7. Class balance / 类别分布

Empirically in tropical Malaysia, `is_rain_event = 1` holds in approximately 20-30 % of hours (more in monsoon months, less in dry season). We pass `class_weight='balanced'` to the Random Forest to prevent it from collapsing to a trivial "always predict no-rain" classifier.

## 8. Reproducibility / 可复现性

```bash
# Real ERA5 path (preferred)
python scripts/1_download_dataset.py    # ~5-10 min, network-bound
python scripts/2_preprocess.py          # < 30 s
python scripts/3_train_model.py         # ~30-90 s on a modern laptop
```

All scripts are idempotent — re-running them does not duplicate data or re-download files that already exist locally.

## 9. Offline / synthetic-data fallback / 离线合成数据回退

For environments without network access (e.g. exam labs, restricted classroom networks) we ship `scripts/1b_synth_dataset.py`, a deterministic physics-informed synthetic generator (seed = 42, see file header for the meteorological assumptions encoded).

The synthetic dataset:
- has the **identical schema** as the Open-Meteo download,
- preserves Malaysia's bimodal monsoon seasonality, tropical diurnal cycle, lapse rate, hydrostatic pressure decay, and zero-inflated rain distribution,
- yields a comparable class balance (~26 % positive),
- lets the **entire pipeline + frontend + tests** be exercised without any external network calls.

It is **not** a substitute for real ERA5 data in the final thesis evaluation. The recommended workflow once network is restored is:

```bash
rm data/raw_*.csv data/processed.csv         # clear synthetic data
python scripts/1_download_dataset.py         # fetch real ERA5 via Open-Meteo
python scripts/2_preprocess.py
python scripts/3_train_model.py              # retrain on real data
```
