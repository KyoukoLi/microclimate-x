# Project pipeline order — "App is the last"
# 项目流程顺序 —— "App 放在最后"

> Direct response to supervisor feedback 4/15: "First identify a dataset.
> And then train the model. And then predict it. Once everything is
> finished, you can develop the app. App is the last."
>
> 4/15 导师反馈直接回应：先 dataset，再 model，再 predict，最后才是 app。

---

## Current state (May 2026) / 当前状态（2026 年 5 月）

```
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 1 — DATASET                                            ✅ DONE  │
│ ────────────────────────────────────────────                         │
│ Source       : Open-Meteo Historical Archive (ECMWF ERA5)            │
│ Coverage     : 5 Malaysian mountain sites, 5 years hourly            │
│ Rows         : 175 315                                               │
│ Target Y     : is_rain_event ∈ {0, 1}  (next-hour rain > 0.1 mm)     │
│ Code         : scripts/{1_download, 1b_synth, 2_preprocess}.py        │
│ Documentation: docs/dataset.md                                       │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 2 — MODEL TRAINING                                     ✅ DONE  │
│ ────────────────────────────────────────────                         │
│ Algorithm    : Random Forest, class_weight='balanced'                │
│ Split        : Time-based, last 20% chronological holdout            │
│ CV           : 5-fold TimeSeriesSplit on training portion            │
│ Test results : ROC AUC 0.871 · PR AP 0.750 · Brier 0.138             │
│ Operating pt : τ = 0.20  →  F2 = 0.778, Recall = 0.934               │
│ Code         : scripts/3_train_model.py                              │
│ Documentation: models/MODEL_CARD.md                                  │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 3 — MODEL EVALUATION                                   ✅ DONE  │
│ ────────────────────────────────────────────                         │
│ Figures      : 6 publication-quality PNGs in figures/                │
│   01_roc_curve.png         · ROC + AUC                               │
│   02_pr_curve.png          · Precision-Recall + AP                   │
│   03_calibration_curve.png · Reliability + Brier                     │
│   04_threshold_sweep.png   · F1/F2/Precision/Recall vs threshold     │
│   05_feature_importance.png· Top-20 features                         │
│   06_confusion_matrix.png  · CM at F2-optimal threshold              │
│ Summary      : figures/evaluation_summary.json                       │
│ Code         : scripts/4_evaluate_model.py                           │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 4 — RULE ENGINE (D5 proposal §3.7 P4.1-P4.6)           ✅ DONE  │
│ ────────────────────────────────────────────                         │
│ P4.1 Load dynamic risk rules  → backend/config.py                    │
│ P4.2 Fetch user context        → ?activity= query parameter          │
│ P4.3 Evaluate environmental    → 4 score_*_risk() functions          │
│         risks (rainfall, fog, wind gust, thunderstorm)               │
│ §3.7.2  Decision table R1-R4   → apply_decision_table_3_7_2()        │
│ Veto cascade                   → _collect_veto_triggers()            │
│ P4.4 Activity weighting        → apply_activity_weighting()          │
│ P4.5 Composite risk score      → dominant-hazard + secondary         │
│ P4.6 Actionable advice         → _normal_advice / _veto_advice       │
│ Code         : backend/rule_engine.py                                │
│ Documentation: docs/architecture.md, docs/thresholds.md              │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 5 — APP (LAST, as instructed)                          ✅ DONE  │
│ ────────────────────────────────────────────                         │
│ Backend     : FastAPI + uvicorn — wraps trained model from Step 2    │
│                + rule engine from Step 4                             │
│ Frontend    : Vue 3 SPA — bilingual EN/ZH, 4 mini-gauges,            │
│                R1-R4 indicators, demo scenarios, error toasts        │
│ Container   : Multi-stage Dockerfile + docker-compose.yml            │
│ Tests       : 70 tests, 97% backend coverage                         │
│ CI          : .github/workflows/ci.yml                               │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 6 — EVALUATION FOR THESIS CHAPTER 5                    🔄 PLAN  │
│ ────────────────────────────────────────────                         │
│ 6a · Hindcast validation against NaDMA flood / landslide archives    │
│ 6b · Small user study with mountain hikers (1-month panel)           │
│ 6c · Comparative ablation: RF only vs Rule only vs Hybrid            │
│ 6d · Threshold sensitivity analysis (τ ∈ {0.10, 0.15, 0.20, 0.25})   │
└──────────────────────────────────────────────────────────────────────┘
```

## Reading order for the supervisor / 给导师过的阅读顺序

When walking the supervisor through the project, **strictly follow Steps 1 → 5**:

| # | Open this | Spend |
|---|---|---|
| 1 | `docs/dataset.md` §4 schema, §5 Y derivation | 60 s |
| 2 | `figures/01_roc_curve.png` + `figures/03_calibration_curve.png` | 30 s |
| 3 | `figures/04_threshold_sweep.png` + `figures/05_feature_importance.png` | 60 s |
| 4 | `docs/architecture.md` §"Engine B internals" — show P4.1→P4.6 mapping | 60 s |
| 5 | `frontend/index.html` running locally — demo with the Genting & Everest scenarios | 60-90 s |

Total ≈ 5 minutes before any Q&A. App is opened **last** as agreed.

按这个顺序给导师过，**严格按 1→5**，整体大概 5 分钟过完再进入 Q&A。**app 一定放最后开**，跟导师上次说的完全一致。
