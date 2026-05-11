# MicroClimate-X — common dev tasks. Run `make help` for a full list.
#
# Conventions:
#   * `make <target>` is the single source of truth for a workflow step.
#   * Targets are idempotent; running twice should not break anything.
#   * Heavy tasks (train, eval) write into git-ignored directories.

PYTHON  ?= ./.venv/bin/python
PIP     ?= ./.venv/bin/pip
UVICORN ?= ./.venv/bin/uvicorn
PYTEST  ?= ./.venv/bin/pytest
RUFF    ?= ./.venv/bin/ruff

.DEFAULT_GOAL := help

.PHONY: help venv install install-dev test test-fast lint format coverage \
        synth preprocess train evaluate run clean docker docker-run

help:                          ## Show this help.
	@awk 'BEGIN{FS=":.*##";print "MicroClimate-X — available targets:"} /^[a-zA-Z_-]+:.*?##/{printf "  \033[36m%-15s\033[0m %s\n",$$1,$$2}' $(MAKEFILE_LIST)

venv:                          ## Create a Python 3.10+ venv at ./.venv
	python3 -m venv .venv
	$(PIP) install --upgrade pip

install: venv                  ## Install runtime dependencies.
	$(PIP) install -r requirements.txt

install-dev: install           ## Install runtime + dev dependencies.
	$(PIP) install -r requirements-dev.txt

# ── Quality ────────────────────────────────────────────────────────────
lint:                          ## Run ruff lint check.
	$(RUFF) check backend/ scripts/ tests/

format:                        ## Format code with ruff.
	$(RUFF) format backend/ scripts/ tests/
	$(RUFF) check --fix backend/ scripts/ tests/

test:                          ## Run the full test suite with coverage.
	$(PYTEST) tests/ --cov=backend --cov-report=term-missing

test-fast:                     ## Run tests quietly, no coverage.
	$(PYTEST) tests/ -q

coverage:                      ## Generate an HTML coverage report.
	$(PYTEST) tests/ --cov=backend --cov-report=html
	@echo "Open htmlcov/index.html in your browser."

# ── ML pipeline ────────────────────────────────────────────────────────
synth:                         ## Generate synthetic dataset (no network).
	$(PYTHON) scripts/1b_synth_dataset.py

preprocess:                    ## Build features + target (data/processed.csv).
	$(PYTHON) scripts/2_preprocess.py

train:                         ## Train the Random Forest model.
	$(PYTHON) scripts/3_train_model.py

evaluate:                      ## Generate publication figures + threshold sweep.
	$(PYTHON) scripts/4_evaluate_model.py

# ── Local run ──────────────────────────────────────────────────────────
run:                           ## Start the FastAPI dev server with auto-reload.
	$(UVICORN) backend.main:app --reload --host 127.0.0.1 --port 8000

# ── Docker ─────────────────────────────────────────────────────────────
docker:                        ## Build the Docker image.
	docker build -t microclimate-x:latest .

docker-run: docker             ## Build then run the container on port 8000.
	docker compose up --build

# ── Housekeeping ───────────────────────────────────────────────────────
clean:                         ## Remove caches, coverage, and SQLite WAL files.
	rm -rf .pytest_cache htmlcov .coverage coverage.xml
	rm -f  cache.sqlite3 cache.sqlite3-*
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
