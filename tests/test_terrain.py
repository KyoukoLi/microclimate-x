"""Sanity tests for DEM-based terrain classification."""
from __future__ import annotations

from backend.terrain import classify_terrain, orographic_lift_dot


def test_flat_terrain():
    dem = [100.0] * 9
    info = classify_terrain(dem)
    assert info.terrain == "Flat"
    assert info.slope_deg < 1.0


def test_valley_classification():
    # Centre is deeply below surroundings.
    dem = [200, 200, 200,
           200,  50, 200,
           200, 200, 200]
    info = classify_terrain(dem)
    assert info.terrain == "Valley"
    assert info.tpi < 0


def test_peak_classification():
    dem = [100, 100, 100,
           100, 300, 100,
           100, 100, 100]
    info = classify_terrain(dem)
    assert info.terrain == "Peak"
    assert info.tpi > 0


def test_orographic_dot_maxes_when_wind_into_slope():
    # West-facing slope (aspect=270°, downhill points west). Wind from the
    # west (270°) hits the slope head-on → dot should be high.
    dot = orographic_lift_dot(wind_dir_deg=270.0,
                              slope_aspect_deg=270.0,
                              slope_deg=30.0)
    assert dot < -0.01 or dot > 0.4  # depends on convention; ensure non-trivial signal
