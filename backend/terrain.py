"""
DEM-based terrain classification.

Given a 3×3 elevation matrix centred on the query point, we classify the
terrain as Valley / Slope / Flat / Peak and compute the slope vector
needed for orographic-uplift detection.

The classification heuristic follows the **Topographic Position Index
(TPI)** approach from Weiss (2001) and is the same technique used in the
microclimate-modelling literature (e.g. Maclean et al., 2018, "Microclima").
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import httpx

from . import config


@dataclass
class TerrainInfo:
    elevation_m: float
    terrain:    str          # "Valley" | "Slope" | "Flat" | "Peak" | "Unknown"
    slope_deg:  float        # 0-90
    aspect_deg: float        # 0-360, direction the slope faces (downhill)
    tpi:        float        # signed, positive = ridge, negative = valley


# ────────────────────────────────────────────────────────────────────────
# DEM fetching
# ────────────────────────────────────────────────────────────────────────

def _build_3x3_grid(lat: float, lon: float, step_deg: float = 0.01) -> list[tuple[float, float]]:
    """Eight neighbours + centre, ordered row-major (NW, N, NE, W, C, E, SW, S, SE).

    Handles the antimeridian (lon ∈ [-180, 180]) and clips latitudes that
    would walk off the poles. Without this, querying e.g. (89.999, 179.999)
    would produce DEM coordinates that the upstream API rejects.
    """
    points = []
    for dlat in (+step_deg, 0.0, -step_deg):       # north → south
        for dlon in (-step_deg, 0.0, +step_deg):   # west  → east
            new_lat = max(-90.0, min(90.0, lat + dlat))
            new_lon = lon + dlon
            # Wrap longitudes into (-180, 180] range.
            if new_lon > 180.0:
                new_lon -= 360.0
            elif new_lon < -180.0:
                new_lon += 360.0
            points.append((new_lat, new_lon))
    return points


async def fetch_dem_3x3(lat: float, lon: float, client: httpx.AsyncClient,
                       step_deg: float = 0.01) -> list[float]:
    """Returns 9 elevation values for the 3×3 grid around (lat, lon)."""
    pts = _build_3x3_grid(lat, lon, step_deg)
    locations = "|".join(f"{p[0]},{p[1]}" for p in pts)
    resp = await client.get(
        config.OPEN_TOPO_URL,
        params={"locations": locations},
        timeout=15.0,
    )
    resp.raise_for_status()
    data = resp.json()
    elevations = []
    for r in data.get("results", []):
        e = r.get("elevation")
        # Open-Topo returns None for ocean points and other no-data tiles.
        elevations.append(float(e) if e is not None else 0.0)
    if len(elevations) != 9:
        raise ValueError(
            f"DEM API returned {len(elevations)} cells, expected 9. "
            "Coordinates may be over ocean or outside coverage."
        )
    return elevations


# ────────────────────────────────────────────────────────────────────────
# Classification
# ────────────────────────────────────────────────────────────────────────

def classify_terrain(dem9: list[float], cell_size_m: float = 1100.0) -> TerrainInfo:
    """
    Indices for the 3x3 matrix:
        0 1 2          (NW, N,  NE)
        3 4 5          (W,  C,  E )
        6 7 8          (SW, S,  SE)
    """
    if len(dem9) != 9:
        raise ValueError(f"DEM matrix must be 3x3, got {len(dem9)} cells")
    nw, n, ne, w, c, e, sw, s, se = dem9

    # Horn's algorithm — surface derivatives.
    dzdx = ((ne + 2 * e + se) - (nw + 2 * w + sw)) / (8 * cell_size_m)
    dzdy = ((sw + 2 * s + se) - (nw + 2 * n + ne)) / (8 * cell_size_m)

    slope_rad = math.atan(math.hypot(dzdx, dzdy))
    slope_deg = math.degrees(slope_rad)

    # Aspect: compass bearing pointing DOWNHILL (0=N, 90=E, 180=S, 270=W).
    aspect_rad = math.atan2(dzdy, -dzdx)  # math convention
    aspect_deg = (math.degrees(aspect_rad) + 360.0) % 360.0

    # Topographic Position Index (TPI): centre cell minus mean of neighbours.
    neighbours = [nw, n, ne, w, e, sw, s, se]
    tpi = c - sum(neighbours) / 8.0

    if abs(tpi) < 5 and slope_deg < 5:
        terrain = "Flat"
    elif tpi < -10:
        terrain = "Valley"
    elif tpi > 20:
        terrain = "Peak"
    else:
        terrain = "Slope"

    return TerrainInfo(
        elevation_m=c,
        terrain=terrain,
        slope_deg=slope_deg,
        aspect_deg=aspect_deg,
        tpi=tpi,
    )


def orographic_lift_dot(wind_dir_deg: float, slope_aspect_deg: float,
                        slope_deg: float) -> float:
    """
    Returns a unitless 'orographic uplift' index in [-1, +1].

    Aspect points DOWNHILL — the slope NORMAL (uphill direction) is the
    opposite bearing. If wind blows opposite to aspect (i.e. into the slope),
    the dot product approaches +1, scaled by slope steepness.

    A high positive value means wind is being forced upward → enhanced rain
    on the windward face.
    """
    wind_rad   = math.radians(wind_dir_deg)
    uphill_rad = math.radians((slope_aspect_deg + 180.0) % 360.0)

    # Wind direction in meteorology = direction FROM which wind blows, so
    # the wind-vector pointing direction is (wind_dir + 180°). For the dot
    # product we just need the cosine of the angle between (wind FROM) and
    # (uphill direction).
    cos_angle = math.cos(wind_rad - uphill_rad)

    # Scale by slope steepness — a 1° slope barely matters.
    return cos_angle * math.sin(math.radians(min(slope_deg, 60.0)))
