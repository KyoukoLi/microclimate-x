"""
SQLite-backed grid cache with risk-adaptive TTL.

Design notes
------------
* WAL journal mode lets concurrent reads proceed during writes — critical
  for FastAPI's async I/O. Default rollback-journal mode would serialise
  every reader behind a writer.
* All blocking sqlite3 calls are wrapped in `asyncio.to_thread` so they
  never stall the event loop.
* Cache key quantises (lat, lon) to a fixed grid resolution (~1.1 km).
  Without quantisation, floating-point jitter destroys hit rate.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from . import config

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS grid_cache (
    grid_key   TEXT PRIMARY KEY,
    payload    TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_expires ON grid_cache(expires_at);

CREATE TABLE IF NOT EXISTS inference_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        INTEGER NOT NULL,
    lat       REAL NOT NULL,
    lon       REAL NOT NULL,
    risk      INTEGER NOT NULL,
    veto      INTEGER NOT NULL,
    summary   TEXT NOT NULL
);
"""


def _grid_key(lat: float, lon: float) -> str:
    res = config.GRID_RESOLUTION_DEG
    return f"{int(round(lat / res))}:{int(round(lon / res))}"


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=5.0, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def _init_blocking(db_path: Path) -> None:
    conn = _connect(db_path)
    try:
        conn.executescript(_INIT_SQL)
    finally:
        conn.close()


async def init_db(db_path: Path = config.DB_PATH) -> None:
    """Create tables and switch to WAL. Idempotent."""
    await asyncio.to_thread(_init_blocking, db_path)


def _get_blocking(db_path: Path, key: str) -> tuple[dict[str, Any], int] | None:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT payload, expires_at FROM grid_cache WHERE grid_key=?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        payload, expires_at = row
        if expires_at <= int(time.time()):
            return None
        ttl_remaining = expires_at - int(time.time())
        return json.loads(payload), ttl_remaining
    finally:
        conn.close()


async def get(lat: float, lon: float) -> tuple[dict[str, Any], int] | None:
    return await asyncio.to_thread(_get_blocking, config.DB_PATH, _grid_key(lat, lon))


def _set_blocking(db_path: Path, key: str, payload: dict[str, Any], ttl_sec: int) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO grid_cache(grid_key, payload, expires_at) "
            "VALUES (?, ?, ?)",
            (key, json.dumps(payload), int(time.time()) + ttl_sec),
        )
    finally:
        conn.close()


async def set(lat: float, lon: float, payload: dict[str, Any], ttl_sec: int) -> None:
    await asyncio.to_thread(_set_blocking, config.DB_PATH, _grid_key(lat, lon), payload, ttl_sec)


def adaptive_ttl(risk_score: int, has_veto: bool) -> int:
    """Higher risk → shorter TTL. We must not serve stale 'Safe' results
    while severe weather is developing."""
    if has_veto or risk_score >= 70:
        return config.TTL_HIGH_RISK_SEC
    if risk_score >= 40:
        return config.TTL_MID_RISK_SEC
    return config.TTL_LOW_RISK_SEC


def _log_blocking(db_path: Path, lat: float, lon: float, risk: int,
                  veto: bool, summary: str) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO inference_log(ts, lat, lon, risk, veto, summary) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (int(time.time()), lat, lon, risk, int(veto), summary),
        )
    finally:
        conn.close()


async def log_inference(lat: float, lon: float, risk: int,
                        veto: bool, summary: str) -> None:
    await asyncio.to_thread(_log_blocking, config.DB_PATH, lat, lon,
                            risk, veto, summary)
