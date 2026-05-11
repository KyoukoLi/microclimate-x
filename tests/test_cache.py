"""Tests for backend.cache — TTL, prune, stats.

These tests pass an explicit db_path to every cache function so they
don't depend on (or pollute) the module-level config.DB_PATH used by
the FastAPI integration tests.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from backend import cache, config


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "test_cache.sqlite3"
    asyncio.run(cache.init_db(p))
    return p


def test_grid_key_quantises_to_cell_size():
    a = cache._grid_key(3.40001, 101.78001, "hiker")
    b = cache._grid_key(3.40009, 101.78009, "hiker")
    assert a == b, "Tiny jitter must fall in the same cell"


def test_grid_key_separates_activities():
    a = cache._grid_key(3.4, 101.8, "hiker")
    b = cache._grid_key(3.4, 101.8, "driver")
    assert a != b


def test_set_then_get_round_trip(db_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", db_path)
    payload = {"risk_score": 42, "risk_level": "Caution", "advice_en": "x"}
    asyncio.run(cache.set(1.1, 2.2, payload, ttl_sec=60, activity="hiker"))
    hit = asyncio.run(cache.get(1.1, 2.2, activity="hiker"))
    assert hit is not None
    got, ttl = hit
    assert got["risk_score"] == 42
    assert 0 < ttl <= 60


def test_get_returns_none_when_expired(db_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", db_path)
    asyncio.run(cache.set(1.1, 2.2, {"a": 1}, ttl_sec=1, activity="hiker"))
    time.sleep(1.2)
    hit = asyncio.run(cache.get(1.1, 2.2, activity="hiker"))
    assert hit is None


def test_adaptive_ttl_scaling():
    assert cache.adaptive_ttl(50, True)  == config.TTL_HIGH_RISK_SEC
    assert cache.adaptive_ttl(85, False) == config.TTL_HIGH_RISK_SEC
    assert cache.adaptive_ttl(50, False) == config.TTL_MID_RISK_SEC
    assert cache.adaptive_ttl(10, False) == config.TTL_LOW_RISK_SEC


def test_cache_stats_returns_counts(db_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", db_path)
    asyncio.run(cache.set(1.1, 2.2, {"x": 1}, ttl_sec=60))
    asyncio.run(cache.set(3.3, 4.4, {"x": 2}, ttl_sec=60))
    stats = asyncio.run(cache.cache_stats(db_path))
    assert stats["rows_live"] >= 2
    assert stats["db_bytes"] > 0


def test_prune_expired_removes_stale_rows(db_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", db_path)
    asyncio.run(cache.set(1.1, 2.2, {"x": 1}, ttl_sec=1))
    asyncio.run(cache.set(3.3, 4.4, {"x": 2}, ttl_sec=300))
    time.sleep(1.2)
    pruned = asyncio.run(cache.prune_expired(db_path))
    assert pruned >= 1


def test_inference_log_persists(db_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", db_path)
    asyncio.run(cache.log_inference(1.1, 2.2, 50, False, "test"))
    stats = asyncio.run(cache.cache_stats(db_path))
    assert stats["inference_log_rows"] >= 1
