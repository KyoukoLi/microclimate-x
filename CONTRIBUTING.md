# Contributing to MicroClimate-X

Thanks for your interest! This is a Final Year Project (UKM) and we
welcome both academic feedback and code contributions.

## Quick setup

```bash
git clone https://github.com/KyoukoLi/microclimate-x
cd microclimate-x
make install-dev          # creates ./.venv, installs runtime + dev deps
make test                 # runs the full suite; should be 70+ passes
make lint                 # ruff check
make run                  # uvicorn dev server on http://localhost:8000
```

The full developer toolbox is in the [Makefile](./Makefile) — `make help`
lists every target.

## Project rhythm

| Layer | Source of truth |
|---|---|
| Engineering thresholds & academic citations | `backend/config.py` + `docs/thresholds.md` |
| Hybrid engine flow & section mapping | `backend/rule_engine.py` + `docs/architecture.md` |
| ML pipeline (features ↔ training ↔ evaluation) | `scripts/2_preprocess.py` ↔ `scripts/3_train_model.py` ↔ `scripts/4_evaluate_model.py` |
| Frontend contract | `backend/schemas.py` (Pydantic) is consumed verbatim by `frontend/index.html` |

If you change something in one column, please update the corresponding
artefact in the same column.

## Pull-request checklist

1. **All tests pass**: `make test` — 70 / 70.
2. **Linter is clean**: `make lint` — 0 ruff errors.
3. **New behaviour is tested.** Add a unit test or an HTTP integration
   test that fails *without* your change.
4. **Public APIs documented.** Update `docs/` and the OpenAPI docstrings
   if you change request / response shapes.
5. **Thresholds are cited.** Any new numeric threshold in `config.py`
   needs an `# Citation:` block referencing peer-reviewed literature or
   an authoritative regulation.
6. **No secrets, no large binaries.** Pre-commit hooks (`make install-dev`
   then `pre-commit install`) enforce both.

## Safety-critical code review

This is decision-support software for outdoor activity. Reviewers should
specifically check:

* **Does this change weaken the Veto cascade?** If a behavioural change
  could let a "Safe" verdict fire in a situation that previously fired
  Danger, the PR needs an explicit test demonstrating the new threshold
  is still life-safety-compliant.
* **Does this change leak temporal autocorrelation?** Random train/test
  splits on time-series data are *forbidden*; always use the time-based
  split in `scripts/3_train_model.py`.

## Reporting issues

Bugs, academic critique, or threshold disputes — please open an issue
with the **scenario**, the **expected verdict**, and the **observed
verdict**. Citations to the relevant safety literature are very welcome.
