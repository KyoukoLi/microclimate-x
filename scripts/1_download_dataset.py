"""
Step 1 / Dataset Download
==========================
Downloads hourly historical weather data from Open-Meteo Historical Weather API
(backed by ECMWF ERA5 reanalysis) for 5 Malaysian mountain locations,
plus elevation data from Open-Topo-Data (SRTM DEM).

Parameters as confirmed with supervisor:
    - Location: Malaysia (mountain regions)
    - Time range: 2020-01-01 to 2023-12-31
    - Variables: temperature_2m, relative_humidity_2m, precipitation,
                 wind_speed_10m, wind_direction_10m, surface_pressure

Output: data/raw_<site>.csv  (one file per location)

Run:  python scripts/1_download_dataset.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# Malaysian mountain locations (lat, lon, name).
# Chosen to span Peninsular Malaysia + Borneo and cover diverse terrain:
# valleys, highlands, and one extreme peak for OOD reference.
SITES = [
    ("genting_highlands", 3.4225, 101.7935),
    ("cameron_highlands", 4.4694, 101.3776),
    ("frasers_hill",      3.7256, 101.7378),
    ("klang_valley",      3.0738, 101.5183),
    ("mt_kinabalu_base",  6.0535, 116.5586),
]

START_DATE = "2020-01-01"
END_DATE   = "2023-12-31"

HOURLY_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
    "wind_direction_10m",
    "surface_pressure",
    "dew_point_2m",
    "cloud_cover",
    "cape",
]

OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_TOPO_URL  = "https://api.opentopodata.org/v1/srtm30m"


def fetch_elevation(lat: float, lon: float) -> float:
    """Fetch ground elevation in meters from Open-Topo-Data (SRTM 30m)."""
    resp = httpx.get(
        OPEN_TOPO_URL,
        params={"locations": f"{lat},{lon}"},
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return float(data["results"][0]["elevation"])


def fetch_hourly(lat: float, lon: float) -> pd.DataFrame:
    """Fetch hourly historical weather data for the configured date range."""
    resp = httpx.get(
        OPEN_METEO_URL,
        params={
            "latitude":   lat,
            "longitude":  lon,
            "start_date": START_DATE,
            "end_date":   END_DATE,
            "hourly":     ",".join(HOURLY_VARS),
            "timezone":   "Asia/Kuala_Lumpur",
            "windspeed_unit": "kmh",
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    payload = resp.json()
    df = pd.DataFrame(payload["hourly"])
    df["time"] = pd.to_datetime(df["time"])
    return df


def download_site(name: str, lat: float, lon: float) -> Path:
    out = DATA_DIR / f"raw_{name}.csv"
    if out.exists():
        print(f"  [skip] {name}: already exists at {out}")
        return out

    print(f"  [elev] fetching elevation for {name} ({lat}, {lon})…")
    elev = fetch_elevation(lat, lon)
    print(f"         elevation = {elev:.1f} m")

    print(f"  [hourly] fetching weather time-series for {name}…")
    df = fetch_hourly(lat, lon)

    df.insert(0, "site",         name)
    df.insert(1, "latitude",     lat)
    df.insert(2, "longitude",    lon)
    df.insert(3, "elevation_m",  elev)

    df.to_csv(out, index=False)
    print(f"  [save] {len(df):>6} rows → {out}")
    return out


def main() -> int:
    print(f"Downloading {len(SITES)} sites from Open-Meteo + Open-Topo-Data…")
    print(f"  date range: {START_DATE} → {END_DATE}")
    print(f"  variables:  {', '.join(HOURLY_VARS)}\n")

    for name, lat, lon in SITES:
        print(f"[ {name} ]")
        try:
            download_site(name, lat, lon)
        except httpx.HTTPError as exc:
            print(f"  [error] {exc}", file=sys.stderr)
            return 1
        time.sleep(1.0)  # be polite to the public APIs

    print("\nDone. Next step:")
    print("  python scripts/2_preprocess.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
