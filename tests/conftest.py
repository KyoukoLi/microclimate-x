"""
Session-wide test fixtures.

The MOST IMPORTANT thing this file does is set `MICROCLIMATEX_DB` to a
temporary, per-session SQLite file BEFORE any `backend.*` modules are
imported. The cache module reads `config.DB_PATH` at import time so the
env override only works if set early.
"""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

# Choose a stable per-session DB; remove any previous run's file.
_SESSION_DB = Path(tempfile.gettempdir()) / f"mcx_test_{uuid.uuid4().hex[:8]}.sqlite3"
os.environ["MICROCLIMATEX_DB"] = str(_SESSION_DB)


def pytest_sessionfinish(session, exitstatus):
    # Best-effort cleanup. SQLite WAL produces -wal / -shm sidecars.
    import contextlib
    for ext in ("", "-wal", "-shm"):
        p = Path(str(_SESSION_DB) + ext)
        if p.exists():
            with contextlib.suppress(OSError):
                p.unlink()
