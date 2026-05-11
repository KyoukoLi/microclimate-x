# syntax=docker/dockerfile:1.7

# ─────────────────────────────────────────────────────────────────
# Stage 1 — builder: install Python deps into a self-contained venv
# ─────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Build deps for any C-extension wheels that need compilation
# (scikit-learn / numpy ship wheels for linux/amd64+arm64 so this is usually a no-op).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt

# ─────────────────────────────────────────────────────────────────
# Stage 2 — runtime: minimal image with only the venv + app code
# ─────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    MICROCLIMATEX_DB=/data/cache.sqlite3

# Non-root user for least-privilege execution.
RUN useradd --create-home --shell /bin/bash --uid 10001 mcx \
    && mkdir -p /app /data \
    && chown -R mcx:mcx /app /data

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=mcx:mcx backend/   backend/
COPY --chown=mcx:mcx frontend/  frontend/
COPY --chown=mcx:mcx scripts/   scripts/
COPY --chown=mcx:mcx models/    models/
COPY --chown=mcx:mcx README.md LICENSE ./

USER mcx

EXPOSE 8000
VOLUME ["/data"]

# Container-aware health check — uses the same /api/health endpoint as humans.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; \
sys.exit(0) if urllib.request.urlopen('http://localhost:8000/api/health', timeout=2).status == 200 else sys.exit(1)" || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
