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

## Composite-index validity / 复合指数的效度

The final 0-100 risk score is a **composite indicator**, not a calibrated probability. Following the methodology of established indices (Fire Weather Index — van Wagner, 1987; Heat Index — Steadman, 1979), validity is established through:

1. **Construct validity** — each component has an independent scientific basis.
2. **Discriminant validity** — extreme samples (Mt Everest, hot calm tropical valley) produce extreme outputs in the expected direction.
3. **Face validity** — domain experts agree the categorical bins (Safe / Caution / Warning / Danger) map sensibly onto action recommendations.

A future *hindcast validation* against published Malaysian flood / landslide events is a planned thesis Chapter 5 contribution.
