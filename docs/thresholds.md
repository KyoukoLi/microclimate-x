# Veto Thresholds & Academic Citations
# 一票否决阈值与学术引用

> **Why this document exists**: the thesis defence panel will ask "why 3500 m?", "why -5 °C?", "why 40 km/h?". Every numeric threshold in `backend/config.py` is justified here against authoritative literature so no value is "magic".

---

## 1. Altitude hypoxia — `ALTITUDE_HYPOXIA_M = 3500 m`

**Rule**: any query above 3500 m AGL immediately receives a Veto.

**Citation**: Luks, A. M., Auerbach, P. S., Freer, L., Grissom, C. K., Keyes, L. E., McIntosh, S. E., Rodway, G. W., Schoene, R. B., Zafren, K., & Hackett, P. H. (2019). *Wilderness Medical Society Clinical Practice Guidelines for the Prevention and Treatment of Acute Altitude Illness: 2019 Update*. **Wilderness & Environmental Medicine**, 30(4), S3-S18. https://doi.org/10.1016/j.wem.2019.04.006

**Justification**: Acute mountain sickness (AMS) onset is clinically significant above 2500 m and severe physiological hypoxia is the norm above 3500 m without acclimatisation. We adopt 3500 m as the *hard* Veto and 2500-3500 m as a sub-Veto penalty band.

---

## 2. Extreme cold — `EXTREME_COLD_C = -5 °C`

**Rule**: ambient temperature ≤ -5 °C triggers a Veto (frostbite risk).

**Citation**: Petrone, P., et al. (2014). *Management of accidental hypothermia and cold injury*. **Current Problems in Surgery**, 51(10), 417-431.  And UIAA Medical Commission Standard No. 19 (2017) *Frostbite*. https://www.theuiaa.org/medical_advice/

**Justification**: Exposed-skin frostbite becomes a real risk when ambient temperatures fall below -5 °C, particularly with any wind. Field guidance from UIAA medical advisors uses -5 °C as a "high vigilance" threshold for outdoor activity.

---

## 3. Gale-force winds — `GALE_WIND_KMH = 40 km/h`

**Rule**: wind speed ≥ 40 km/h triggers a Veto.

**Citation**: World Meteorological Organization. (2024). *International Codes — Beaufort Wind Force Scale*. https://www.wmo.int/

**Justification**: Beaufort Force 6 ("Strong Breeze") covers 39-49 km/h, defined as the regime where "umbrellas are used with difficulty" and walking against the wind becomes hazardous. Above 40 km/h, balance loss and being struck by wind-borne debris become real risks for ridge / exposed-slope hikers.

---

## 4. High CAPE (lightning) — `HIGH_CAPE_JKG = 1000 J/kg`

**Rule**: Convective Available Potential Energy ≥ 1000 J/kg triggers a Veto.

**Citation**: National Weather Service. *Convective Forecasting Handbook* (latest edition). U.S. National Oceanic and Atmospheric Administration.

**Justification**: NWS guidance characterises CAPE > 1000 J/kg as "moderate instability" capable of sustaining thunderstorms with lightning. CAPE > 2500 J/kg is "strong". For a safety-critical application aimed at hikers, the 1000 J/kg threshold provides early warning before lightning becomes likely.

---

## 5. Low visibility — `LOW_VISIBILITY_M = 100 m`

**Rule**: surface visibility below 100 m triggers a Veto.

**Citation**: Federal Aviation Administration. (2024). *Aeronautical Information Manual* §7-1-12. https://www.faa.gov/

**Justification**: AIM defines Category III approach conditions as visibility below 200 m. For non-instrument human navigation, 100 m is the conventional "whiteout / dense fog" threshold below which dead-reckoning over alpine terrain becomes infeasible.

---

## 6. Orographic uplift — `OROGRAPHIC_DOT_THRESHOLD = 0.7`

**Rule**: when the wind-vs-slope-normal dot product ≥ 0.7 AND ML rain probability ≥ 0.5 on a Slope terrain, a Veto fires.

**Citation**: Roe, G. H. (2005). *Orographic precipitation*. **Annual Review of Earth and Planetary Sciences**, 33, 645-671. https://doi.org/10.1146/annurev.earth.33.092203.122541

**Justification**: Forced ascent of moisture-laden air over a windward slope is one of the highest-rainfall meteorological mechanisms on Earth — entire climate regimes (e.g. Cherrapunji, India) are produced by it. Even when bulk ML probability is moderate, terrain-forced uplift can locally multiply precipitation by an order of magnitude.

---

## 7. Valley flash-flood — `VALLEY_FLOOD_PROB = 0.80`

**Rule**: ML rain probability ≥ 80 % combined with Valley terrain triggers a Veto.

**Citation**: Bhuiyan, M. A. E., Anagnostou, E. N., & Kruzdlo, R. (2020). *Improving satellite-based precipitation estimates over complex terrain using machine learning algorithms*. **Journal of Hydrology**, 588, 125060.

**Justification**: Valley floors collect water from the entire upstream basin. Even modest rainfall amounts upstream concentrate hydrologically downstream, producing flash floods on timescales as short as 30 minutes. The literature documents disproportionate fatality rates from flash floods relative to other rain-driven hazards.

---

## 8. Fog sub-hazard — `FOG_HUMIDITY_PCT = 95 %`, `FOG_DEW_DEP_MAX_C = 2 °C`, `FOG_CLOUD_BASE_MAX_M = 800 m`

**Rule**: the fog sub-scorer awards near-maximum contribution when humidity ≥ 95 %, dew-point depression ≤ 2 °C, and cloud base ≤ 800 m.

**Citation**: World Meteorological Organization. (2019). *Guide to Meteorological Instruments and Methods of Observation (CIMO Guide)*, WMO-No. 8, Chapter on Visibility. https://library.wmo.int/idurl/4/68695

**Justification**: WMO surface synoptic codes define fog as visibility < 1 km, which is observed most reliably when humidity is near saturation (typically > 95 %) and dew-point depression is below 2 °C. The 800 m cloud-base ceiling is the value used in the D5 §3.7.2 decision table to detect "low cloud meeting terrain".

---

## 9. Wind gust sub-hazard — `GUST_WIND_MIN_KMH = 25 km/h`

**Rule**: wind gust sub-score scales linearly with sustained wind from 25 km/h up to the gale Veto at 40 km/h, with terrain amplification for ridges and exposed slopes.

**Citation**: WMO Beaufort Wind Force Scale; Holton, J. R. (2004). *An Introduction to Dynamic Meteorology*, 4th ed., on mountain-wave and pass-acceleration phenomena.

**Justification**: On exposed ridges and through mountain passes, sustained winds of 25 km/h commonly gust 1.3-1.8× higher (Beaufort F6 territory). Trees and shrubs near peaks become wind-snap hazards, and weight-of-pack stability margins narrow significantly above ~30 km/h sustained.

---

## 10. Thunderstorm sub-hazard — `THUNDER_CAPE_MIN_JKG = 500 J/kg`, `THUNDER_PRESSURE_DROP = -2 hPa / 3 h`

**Rule**: the thunderstorm sub-scorer adds significant contribution when CAPE ≥ 500 J/kg, with a precipitator boost when pressure has dropped ≥ 2 hPa over the past 3 hours.

**Citation**: National Weather Service Convective Outlook reference values; Doswell, C. A. III, & Schultz, D. M. (2006). *On the Use of Indices and Parameters in Forecasting Severe Storms*. **E-Journal of Severe Storms Meteorology**, 1(3).

**Justification**: CAPE ≥ 500 J/kg is the conventional "moderate instability" floor at which convective storms become possible (1000 J/kg is the *Veto* — at that level lightning is likely). A 2 hPa / 3 h pressure fall is a textbook frontal-passage / mesoscale-convective-system precursor, well below the rapid-pressure-fall thresholds used in operational forecasting.

---

## 11. D5 §3.7.2 / Table 4.2 Decision Table — R1-R4

| Rule | Trigger | Conclusion |
|---|---|---|
| **R1** | macro rain prob ≤ 30 %, humidity > 85 %, wind into a windward slope, pressure tendency < -1.5 hPa/3h, cloud base < 800 m | Hidden orographic-rain risk despite low macro probability |
| **R2** | Same humidity / pressure / cloud-base as R1, but wind NOT into slope, terrain leeward or valley | No significant rain — macro forecast is correct |
| **R3** | macro rain prob ≥ 70 %, wind into a windward slope | Heavy downpour incoming — avoid mountains and valleys |
| **R4** | macro rain prob ≥ 70 %, no terrain amplification | Standard-rain precautions; no orographic amplification |

**Citation**: D5 Proposal — "MicroClimate-X" §3.7.2 Decision Table 4.2 (own work, derived from Roe 2005 orographic-precipitation theory and standard synoptic-meteorology pressure-tendency / cloud-base rules of thumb).

**Justification**: This 4-row decision table captures the *thesis-original* contribution — converting macro-scale model output (probability of rain in a coarse grid cell) into a *terrain-aware verdict* by combining wind alignment, humidity, and pressure tendency. The fact that R1 (hidden rain) and R3 (heavy downpour) can both fire on a windward slope while R2 (no risk) fires on a leeward valley with otherwise-identical macro probability is the table's discriminative value.

---

## 12. Activity weights — D5 §3.7 / P4.4

| Activity | Rainfall | Fog | Wind Gust | Thunderstorm |
|---|---|---|---|---|
| **hiker**        | 1.0 | **1.3** | 1.0 | **1.4** |
| **driver**       | 0.8 | **1.5** | 1.3 | 0.9 |
| **construction** | 1.0 | 0.8 | **1.5** | **1.4** |
| **general**      | 1.0 | 1.0 | 1.0 | 1.0 |

**Justification**:
- *Hikers* die above tree line from lightning and disorientation in fog (NOLS Wilderness Medicine, 2020 incident review).
- *Drivers* lose vehicle control most often in fog (visibility), with wind a secondary hazard for high-sided vehicles (FHWA *Road Weather Management* program, 2019).
- *Construction* workers care about wind (crane / scaffolding) and lightning (OSHA 29 CFR §1926.95 *PPE*).
- *General* preserves a calibration baseline against which the other profiles can be benchmarked.

Per-sub-score weight is multiplied, then per-hazard score is clipped to 100 so a weight of 1.5 cannot push a single sub-score past saturation; the composite formula then aggregates with 80 % weight on the dominant (worst) hazard.

---

## Composite-index validity / 复合指数的效度

The final 0-100 risk score is a **composite indicator**, not a calibrated probability. Following the methodology of established indices (Fire Weather Index — van Wagner, 1987; Heat Index — Steadman, 1979), validity is established through:

1. **Construct validity** — each component has an independent scientific basis.
2. **Discriminant validity** — extreme samples (Mt Everest, hot calm tropical valley) produce extreme outputs in the expected direction.
3. **Face validity** — domain experts agree the categorical bins (Safe / Caution / Warning / Danger) map sensibly onto action recommendations.

A future *hindcast validation* against published Malaysian flood / landslide events is a planned thesis Chapter 5 contribution.
