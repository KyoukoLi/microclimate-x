"""
Step 2 / Preprocessing & Feature Engineering
=============================================
Reads raw per-site CSVs, engineers ML-ready features, and derives the binary
target `is_rain_event` from the raw `precipitation` column.

Pipeline:
    1. Load all data/raw_*.csv and concatenate.
    2. Drop rows with NaN in critical fields.
    3. Engineer features:
         - wind_u, wind_v       (decompose circular wind direction)
         - hour_sin, hour_cos   (cyclic time encoding)
         - month_sin, month_cos (captures Malaysia's monsoon seasonality)
         - precipitation_lag_1h (autocorrelation signal)
         - dew_point_depression (T - T_dew, saturation proxy)
         - pressure_change_3h   (storm-approaching signal)
    4. Derive target:
         is_rain_event(t) = 1 iff precipitation(t+1h) > RAIN_THRESHOLD_MM (WMO trace)
    5. Save data/processed.csv

Run:  python scripts/2_preprocess.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

# WMO definition of "trace precipitation": >= 0.1 mm in an hour.
RAIN_THRESHOLD_MM = 0.1


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add domain-informed derived features. Operates per site to avoid
    cross-site leakage in lag/shift operations."""
    out_frames: list[pd.DataFrame] = []
    for _, g in df.groupby("site", sort=False):
        g = g.sort_values("time").reset_index(drop=True).copy()

        # Wind: decompose into u/v components. Raw degrees are circular and
        # mathematically misleading to tree models (0° vs 360° look "far").
        rad = np.deg2rad(g["wind_direction_10m"])
        g["wind_u"] = g["wind_speed_10m"] * np.sin(rad)
        g["wind_v"] = g["wind_speed_10m"] * np.cos(rad)

        # Cyclic time encoding (avoids the 23→0 hour discontinuity).
        h = g["time"].dt.hour
        m = g["time"].dt.month
        g["hour_sin"]  = np.sin(2 * np.pi * h / 24)
        g["hour_cos"]  = np.cos(2 * np.pi * h / 24)
        g["month_sin"] = np.sin(2 * np.pi * m / 12)
        g["month_cos"] = np.cos(2 * np.pi * m / 12)

        # Lag / tendency features (storm precursors).
        g["precipitation_lag_1h"] = g["precipitation"].shift(1).fillna(0.0)
        g["pressure_change_3h"]   = g["surface_pressure"] - g["surface_pressure"].shift(3)
        g["pressure_change_3h"]   = g["pressure_change_3h"].fillna(0.0)

        # Dew point depression: small value = atmosphere near saturation.
        g["dew_point_depression"] = g["temperature_2m"] - g["dew_point_2m"]

        # === Target: predict whether rain occurs in the NEXT hour ===
        # Using shift(-1) explicitly to avoid temporal data leakage:
        # features at time t pair with the rainfall outcome at t+1h.
        next_hour_precip = g["precipitation"].shift(-1)
        g["is_rain_event"] = (next_hour_precip > RAIN_THRESHOLD_MM).astype("Int64")

        # Drop the final row (no t+1h label) and any all-NaN rows.
        g = g.iloc[:-1].copy()
        out_frames.append(g)

    return pd.concat(out_frames, ignore_index=True)


def main() -> int:
    raw_files = sorted(DATA_DIR.glob("raw_*.csv"))
    if not raw_files:
        print("ERROR: no data/raw_*.csv found. Run scripts/1_download_dataset.py first.")
        return 1

    print(f"Loading {len(raw_files)} raw site files…")
    dfs = [pd.read_csv(p, parse_dates=["time"]) for p in raw_files]
    df = pd.concat(dfs, ignore_index=True)
    print(f"  rows total: {len(df):,}")

    # Standardised column names (presentation-friendly + matches design doc).
    df = df.rename(columns={
        "temperature_2m":       "temperature_c",
        "relative_humidity_2m": "humidity_pct",
        "wind_speed_10m":       "wind_speed_kmh",
        "wind_direction_10m":   "wind_direction_deg",
        "surface_pressure":     "pressure_hpa",
        "dew_point_2m":         "dew_point_c",
        "cloud_cover":          "cloud_cover_pct",
        "cape":                 "cape_jkg",
    })

    # Restore originals expected by engineer_features (it uses raw names for clarity).
    df = df.rename(columns={
        "temperature_c":       "temperature_2m",
        "humidity_pct":        "relative_humidity_2m",
        "wind_speed_kmh":      "wind_speed_10m",
        "wind_direction_deg":  "wind_direction_10m",
        "pressure_hpa":        "surface_pressure",
        "dew_point_c":         "dew_point_2m",
        "cloud_cover_pct":     "cloud_cover",
        "cape_jkg":            "cape",
    })

    before = len(df)
    df = df.dropna(subset=[
        "temperature_2m", "relative_humidity_2m", "precipitation",
        "wind_speed_10m", "wind_direction_10m", "surface_pressure",
    ])
    print(f"  rows after dropna: {len(df):,}  (dropped {before - len(df):,})")

    print("Engineering features per site…")
    df = engineer_features(df)

    # Final renaming to the design-doc-friendly column names that the
    # downstream training script and README expect.
    df = df.rename(columns={
        "temperature_2m":       "temperature_c",
        "relative_humidity_2m": "humidity_pct",
        "wind_speed_10m":       "wind_speed_kmh",
        "wind_direction_10m":   "wind_direction_deg",
        "surface_pressure":     "pressure_hpa",
        "dew_point_2m":         "dew_point_c",
        "cloud_cover":          "cloud_cover_pct",
        "cape":                 "cape_jkg",
    })

    # Drop the one terminal row per site that lacks the t+1h label.
    df = df.dropna(subset=["is_rain_event"]).copy()
    df["is_rain_event"] = df["is_rain_event"].astype(int)

    out = DATA_DIR / "processed.csv"
    df.to_csv(out, index=False)

    print("\n=== Processed dataset summary ===")
    print(f"  total samples         : {len(df):,}")
    print(f"  sites                 : {df['site'].nunique()}")
    print(f"  date range            : {df['time'].min()} → {df['time'].max()}")
    print(f"  class balance (Y=1)   : {df['is_rain_event'].mean():.1%}")
    print(f"  saved to              : {out}")
    print("\nFirst rows of (selected cols):")
    cols = ["site", "time", "elevation_m", "temperature_c", "humidity_pct",
            "wind_speed_kmh", "pressure_hpa", "is_rain_event"]
    print(df[cols].head(10).to_string(index=False))

    print("\nNext step:  python scripts/3_train_model.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
