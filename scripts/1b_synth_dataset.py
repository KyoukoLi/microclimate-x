"""
Step 1B / Synthetic Dataset Generator  (offline fallback)
==========================================================

When the real Open-Meteo / Open-Topo-Data APIs are unreachable (e.g. behind
a restrictive corporate proxy or in an offline classroom), this script
generates a physically-plausible synthetic dataset with the *exact same
schema* as scripts/1_download_dataset.py.

This lets the end-to-end pipeline (preprocess + train + serve) be
validated without network access. To switch back to real data later,
delete data/raw_*.csv and run scripts/1_download_dataset.py.

The synthetic generator encodes:
    * Standard atmosphere lapse rate (≈ -6.5 °C / km)
    * Hydrostatic pressure decay with altitude (~ -12 hPa / 100 m)
    * Tropical diurnal temperature cycle (cooler at night, warmer mid-afternoon)
    * Malaysia's bimodal monsoon precipitation seasonality (Apr-May, Oct-Nov peaks)
    * Humidity inversely correlated with temperature, plus monsoon boost
    * Heavy-tailed precipitation distribution (most hours dry, rare extremes)
    * CAPE rising with humid afternoon convection
    * Dew-point depression that shrinks toward saturation as humidity rises

This is *NOT* a substitute for real ERA5 reanalysis data in the final
thesis — its purpose is purely to exercise the ML pipeline end-to-end.

Run:  python scripts/1b_synth_dataset.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# Site (name, lat, lon, approx elevation_m) — same as scripts/1_download_dataset.py
SITES = [
    ("genting_highlands", 3.4225, 101.7935, 1742.0),
    ("cameron_highlands", 4.4694, 101.3776, 1500.0),
    ("frasers_hill",      3.7256, 101.7378, 1300.0),
    ("klang_valley",      3.0738, 101.5183,  120.0),
    ("mt_kinabalu_base",  6.0535, 116.5586, 1800.0),
]

START = pd.Timestamp("2020-01-01 00:00:00")
END   = pd.Timestamp("2023-12-31 23:00:00")


def generate_site(name: str, lat: float, lon: float, elev: float,
                  rng: np.random.Generator) -> pd.DataFrame:
    """Generate hourly synthetic weather time-series for a single site."""
    timestamps = pd.date_range(START, END, freq="h")
    n = len(timestamps)

    hour  = timestamps.hour.to_numpy()
    doy   = timestamps.dayofyear.to_numpy()
    month = timestamps.month.to_numpy()

    # Temperature: tropical baseline 27 °C at sea level, lapse rate to altitude,
    # plus diurnal swing (±4 °C) and seasonal (±1.5 °C).
    sea_level_temp = 27.0
    lapse = -6.5 * (elev / 1000.0)
    diurnal  = -4.0 * np.cos(2 * np.pi * (hour - 3) / 24.0)
    seasonal =  1.5 * np.cos(2 * np.pi * (doy - 60) / 365.25)
    noise_T = rng.normal(0.0, 1.2, n)
    temperature = sea_level_temp + lapse + diurnal + seasonal + noise_T

    # Pressure: hydrostatic decay, plus 3-hourly random walk for synoptic systems.
    sea_level_p = 1010.0
    p_alt = sea_level_p - 12.0 * (elev / 100.0)
    pressure = p_alt + rng.normal(0.0, 0.8, n)
    pressure = pd.Series(pressure).rolling(3, min_periods=1).mean().to_numpy()

    # Monsoon-driven rainy season: Apr-May and Oct-Nov are peak rainfall in
    # Peninsular Malaysia; weight precipitation probability accordingly.
    monsoon_weight = (
        0.5 + 0.5 * np.cos(2 * np.pi * (doy - 305) / 365.25)       # NE monsoon
        + 0.4 * np.exp(-0.5 * ((doy - 135) / 25.0) ** 2)            # SW pre-monsoon
        + 0.4 * np.exp(-0.5 * ((doy - 305) / 30.0) ** 2)
    )

    # Humidity: anti-correlated with diurnal temperature; lifted by monsoon.
    humidity_base = 78.0 + 4.0 * monsoon_weight
    humidity = humidity_base - 0.9 * diurnal + rng.normal(0.0, 5.0, n)
    humidity = np.clip(humidity, 30.0, 100.0)

    # CAPE: builds with afternoon humid heat — peaks 13-16h on humid days.
    afternoon = np.exp(-0.5 * ((hour - 14.5) / 2.5) ** 2)
    cape = (
        afternoon * (humidity - 60.0) * 25.0 * monsoon_weight
        + rng.normal(0.0, 80.0, n)
    )
    cape = np.clip(cape, 0.0, 4500.0)

    # Cloud cover: tied to humidity & monsoon.
    cloud = np.clip(
        0.55 * humidity + 25.0 * monsoon_weight + rng.normal(0.0, 8.0, n),
        0.0, 100.0,
    )

    # Dew point depression shrinks at high humidity (saturation).
    dew_dep = np.clip(36.0 - 0.32 * humidity + rng.normal(0.0, 1.4, n), 0.1, 30.0)
    dew_point = temperature - dew_dep

    # Wind: weak in tropics; daytime sea breeze in lowlands, slightly more wind aloft.
    wind_base = 5.0 + 0.0025 * elev
    wind_speed = np.clip(
        wind_base + 2.5 * afternoon + np.abs(rng.normal(0.0, 2.5, n)),
        0.0, 60.0,
    )
    # Direction: slow random walk so consecutive hours have correlated direction.
    dir_steps = rng.normal(0.0, 25.0, n).cumsum()
    wind_dir = (dir_steps % 360.0 + 180.0 * monsoon_weight) % 360.0

    # Precipitation: zero-inflated; probability rises with humidity × monsoon × CAPE.
    rain_prob = (
        0.04
        + 0.55 * monsoon_weight * (humidity > 80).astype(float)
        + 0.0001 * cape
        + 0.25 * afternoon * (humidity > 85).astype(float)
    )
    rain_prob = np.clip(rain_prob, 0.0, 0.85)
    rain_event = rng.random(n) < rain_prob
    # When it rains, amount follows an exponential distribution (heavy-tailed).
    rain_amount = np.where(
        rain_event,
        rng.exponential(scale=2.8, size=n),  # mm/h
        0.0,
    )

    df = pd.DataFrame({
        "site":                 name,
        "latitude":             lat,
        "longitude":            lon,
        "elevation_m":          elev,
        "time":                 timestamps,
        "temperature_2m":       np.round(temperature, 2),
        "relative_humidity_2m": np.round(humidity, 1),
        "precipitation":        np.round(rain_amount, 2),
        "wind_speed_10m":       np.round(wind_speed, 2),
        "wind_direction_10m":   np.round(wind_dir, 1),
        "surface_pressure":     np.round(pressure, 1),
        "dew_point_2m":         np.round(dew_point, 2),
        "cloud_cover":          np.round(cloud, 1),
        "cape":                 np.round(cape, 0),
    })
    return df


def main() -> int:
    rng = np.random.default_rng(seed=42)
    print(f"Generating SYNTHETIC dataset for {len(SITES)} sites…")
    print(f"  date range: {START.date()} → {END.date()}\n")
    for name, lat, lon, elev in SITES:
        out = DATA_DIR / f"raw_{name}.csv"
        df = generate_site(name, lat, lon, elev, rng)
        df.to_csv(out, index=False)
        rain_pct = (df["precipitation"] > 0.1).mean() * 100.0
        print(f"  [{name:<18}] {len(df):>6} rows  rain-hours={rain_pct:4.1f}%  → {out.name}")
    print("\nDone (synthetic). Next:  python scripts/2_preprocess.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
