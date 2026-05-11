"""
Topographic Rule-Based Expert System — Engine B of the hybrid architecture.

This module is structured to mirror D5 proposal §3.7 / P4 so it is auditable
against the thesis section by section:

    P4.1  Load Dynamic Risk Rules          → constants in backend/config.py
    P4.2  Fetch User Context (activity)    → `evaluate(activity=…)` parameter
    P4.3  Evaluate Environmental Risks     → four `score_*_risk()` functions
                                              (rainfall / fog / wind_gust / thunderstorm)
    P4.4  Apply Activity-Specific Weight   → `apply_activity_weighting()`
    P4.5  Calculate Composite Risk Score   → weighted sum + Veto cap
    P4.6  Generate Actionable Advice       → bilingual advice helpers

In parallel, the Veto cascade (life-safety overrides) and the D5 §3.7.2
Table 4.2 Decision Table run alongside the composite score.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import config
from .schemas import (
    ActivityType,
    DecisionTableMatch,
    HazardSubscores,
    InferenceStep,
    RiskLevel,
    VetoTrigger,
)


@dataclass
class RuleResult:
    risk_score: int = 0
    risk_level: RiskLevel = "Safe"
    veto_triggers:        list[VetoTrigger] = field(default_factory=list)
    inference_log:        list[InferenceStep] = field(default_factory=list)
    advice_en: str = ""
    advice_zh: str = ""
    hazard_subscores:     HazardSubscores = field(
        default_factory=lambda: HazardSubscores(rainfall=0, fog=0, wind_gust=0, thunderstorm=0)
    )
    decision_table_matches: list[DecisionTableMatch] = field(default_factory=list)
    activity: ActivityType = "general"

    @property
    def has_veto(self) -> bool:
        return len(self.veto_triggers) > 0


def _bin_level(score: int) -> RiskLevel:
    if score >= 80:
        return "Danger"
    if score >= 55:
        return "Warning"
    if score >= 30:
        return "Caution"
    return "Safe"


def _clip(x: float) -> int:
    return max(0, min(100, int(round(x))))


# ════════════════════════════════════════════════════════════════════════
# P4.3 — Four Hazard Sub-Scorers (each returns 0-100)
# ════════════════════════════════════════════════════════════════════════

def score_rainfall_risk(
    *, ml_rain_prob: float, terrain: str, orographic_dot: float,
    pressure_change_3h: float, humidity_pct: float,
) -> int:
    """Rainfall sub-score. Backbone is ML probability; terrain amplifies.

    Calibration: ml_rain_prob 0.45 on flat terrain should yield ~40
    (matching the proposal's intuition that 45 % probability already warrants
    a 'Caution' verdict)."""
    s = ml_rain_prob * 55.0                   # baseline 0-55 from ML
    if ml_rain_prob >= 0.70:
        s += 20.0                              # high-confidence rain bonus
    elif ml_rain_prob >= 0.40:
        s += 12.0
    if terrain == "Valley":
        s += 8.0
    elif terrain == "Slope":
        s += orographic_dot * 25.0             # up to +25 on a windward slope
    if pressure_change_3h <= -1.5:             # storm-precursor pressure fall
        s += 8.0
    if humidity_pct >= 90.0:
        s += 6.0
    return _clip(s)


def score_fog_risk(
    *, humidity_pct: float, dew_point_depression: float,
    cloud_cover_pct: float, terrain: str, elevation_m: float,
) -> int:
    """Fog sub-score. Saturated boundary layer + heavy low cloud + a basin
    or slope that traps the radiation/advection fog."""
    if dew_point_depression > 5.0:
        return _clip(humidity_pct - 80.0)    # near-zero unless very humid

    s = 0.0
    # Humidity → saturation contribution.
    if humidity_pct >= config.FOG_HUMIDITY_PCT:
        s += 55.0
    elif humidity_pct >= 90.0:
        s += 25.0
    elif humidity_pct >= 85.0:
        s += 10.0

    # Dew-point depression: smaller = closer to saturation.
    if dew_point_depression <= config.FOG_DEW_DEP_MAX_C:
        s += 25.0
    elif dew_point_depression <= 3.5:
        s += 12.0

    # Low cloud cover suggests a low-lying cloud deck = potential fog when
    # cloud base meets terrain.
    if cloud_cover_pct >= 90.0:
        s += 10.0
    elif cloud_cover_pct >= 70.0:
        s += 5.0

    # Terrain modifier: valleys trap radiation fog; high peaks intersect cloud base.
    if terrain == "Valley":
        s += 10.0
    elif terrain == "Peak" and elevation_m >= 1500.0:
        s += 8.0

    return _clip(s)


def score_wind_gust_risk(
    *, wind_speed_kmh: float, terrain: str, slope_deg: float,
    orographic_dot: float,
) -> int:
    """Wind gust sub-score. Sustained wind × topographic acceleration."""
    if wind_speed_kmh < config.GUST_WIND_MIN_KMH * 0.6:
        # Calm conditions — even ridges won't produce dangerous gusts.
        return _clip(wind_speed_kmh)

    # Baseline: linear in sustained wind, saturating at the gale Veto level.
    s = (wind_speed_kmh / config.GALE_WIND_KMH) * 55.0

    # Topographic acceleration on ridges and exposed slopes.
    if terrain in {"Peak", "Slope"}:
        s += min(slope_deg, 30.0)         # up to +30 for very steep slopes
    if terrain == "Slope" and abs(orographic_dot) >= 0.5:
        s += 8.0                            # pass / saddle wind funnel

    return _clip(s)


def score_thunderstorm_risk(
    *, cape_jkg: float, pressure_change_3h: float, humidity_pct: float,
) -> int:
    """Thunderstorm sub-score. Atmospheric instability + storm precursors."""
    s = 0.0

    # CAPE — primary indicator. Linear up to NWS "strong instability" 2500 J/kg.
    if cape_jkg >= config.HIGH_CAPE_JKG:
        s += 60.0
    elif cape_jkg >= config.THUNDER_CAPE_MIN_JKG:
        s += 35.0 + (cape_jkg - config.THUNDER_CAPE_MIN_JKG) / 20.0
    elif cape_jkg >= 200.0:
        s += 12.0

    # Falling pressure precedes convective initiation.
    if pressure_change_3h <= config.THUNDER_PRESSURE_DROP:
        s += 20.0
    elif pressure_change_3h <= -1.0:
        s += 8.0

    # Humidity gates whether instability can actually produce a thunderstorm.
    if humidity_pct >= 80.0:
        s += 10.0

    return _clip(s)


# ════════════════════════════════════════════════════════════════════════
# D5 §3.7.2 / Table 4.2 — Decision Table R1-R4
# ════════════════════════════════════════════════════════════════════════

def apply_decision_table_3_7_2(
    *,
    macro_rain_prob:    float,
    humidity_pct:       float,
    wind_into_slope:    bool,
    terrain:            str,
    pressure_change_3h: float,
    cloud_base_m:       float | None,
) -> list[DecisionTableMatch]:
    """Returns the list of decision-table rules (R1-R4) that fired.
    One-to-one match against D5 §3.7.2 Table 4.2."""

    terrain_kind = "WindwardSlope" if (terrain == "Slope" and wind_into_slope) else \
                   "LeewardOrValley" if terrain in {"Valley"} or (terrain == "Slope" and not wind_into_slope) else \
                   terrain

    matches: list[DecisionTableMatch] = []
    for rule_id, rule in config.DECISION_TABLE_3_7_2.items():
        ok = True
        if rule["macro_rain_prob_max"] is not None and macro_rain_prob > rule["macro_rain_prob_max"]:
            ok = False
        if rule["macro_rain_prob_min"] is not None and macro_rain_prob < rule["macro_rain_prob_min"]:
            ok = False
        if rule["humidity_min_pct"] is not None and humidity_pct < rule["humidity_min_pct"]:
            ok = False
        if rule["wind_into_slope"] is not None and wind_into_slope != rule["wind_into_slope"]:
            ok = False
        if rule["terrain"] is not None and terrain_kind != rule["terrain"]:
            ok = False
        if rule["pressure_change_3h_max"] is not None and pressure_change_3h > rule["pressure_change_3h_max"]:
            ok = False
        if rule["cloud_base_max_m"] is not None and (cloud_base_m is None or cloud_base_m > rule["cloud_base_max_m"]):
            ok = False
        if ok:
            matches.append(DecisionTableMatch(
                rule=rule_id,
                description=rule["description"],
                conclusion_en=rule["conclusion_en"],
                conclusion_zh=rule["conclusion_zh"],
            ))
    return matches


# ════════════════════════════════════════════════════════════════════════
# P4.4 — Activity-aware composite scoring
# ════════════════════════════════════════════════════════════════════════

def apply_activity_weighting(
    subs: HazardSubscores, activity: ActivityType,
) -> int:
    """Composite 0-100 score.

    Design rationale: a naive mean dilutes the dominant hazard — e.g. an
    extreme thunderstorm risk (90) averaged with three safe (10) values
    would yield 30, which understates the actual danger. We therefore use
    a **dominant-hazard + secondary-contribution** formulation:

        composite = 0.80 · max(weighted sub-scores)
                  + 0.20 · mean(weighted sub-scores excluding max)

    This ensures the worst hazard for the user's activity drives the score,
    while still allowing multiple moderate hazards to push the score up.
    """
    w = config.ACTIVITY_WEIGHTS[activity]
    weighted = [
        min(100.0, w["rainfall"]     * subs.rainfall),
        min(100.0, w["fog"]          * subs.fog),
        min(100.0, w["wind_gust"]    * subs.wind_gust),
        min(100.0, w["thunderstorm"] * subs.thunderstorm),
    ]
    top  = max(weighted)
    rest = sum(weighted) - top
    others_mean = rest / 3.0
    return _clip(top * 0.80 + others_mean * 0.20)


# ════════════════════════════════════════════════════════════════════════
# Veto cascade (life-safety overrides) — same as before, unchanged behaviour
# ════════════════════════════════════════════════════════════════════════

def _collect_veto_triggers(
    *, elevation_m: float, terrain: str, weather: dict[str, Any],
    ml_rain_prob: float, orographic_dot: float,
) -> list[VetoTrigger]:
    temp_c     = weather.get("temperature_c", 25.0)
    wind_kmh   = weather.get("wind_speed_kmh", 0.0)
    cape       = weather.get("cape_jkg", 0.0)
    visibility = weather.get("visibility_m", 10000.0)
    out: list[VetoTrigger] = []

    if elevation_m > config.ALTITUDE_HYPOXIA_M:
        out.append(VetoTrigger(
            rule="altitude_hypoxia", value=elevation_m,
            message_en=f"Altitude {elevation_m:.0f} m exceeds {config.ALTITUDE_HYPOXIA_M:.0f} m — severe hypoxia risk.",
            message_zh=f"海拔 {elevation_m:.0f} m 超过 {config.ALTITUDE_HYPOXIA_M:.0f} m，存在严重缺氧风险。",
        ))
    if temp_c <= config.EXTREME_COLD_C:
        out.append(VetoTrigger(
            rule="extreme_cold", value=temp_c,
            message_en=f"Temperature {temp_c:.1f}°C — frostbite risk per UIAA guidance.",
            message_zh=f"温度 {temp_c:.1f}°C，UIAA 指南判定为冻伤风险。",
        ))
    if wind_kmh >= config.GALE_WIND_KMH:
        out.append(VetoTrigger(
            rule="gale_wind", value=wind_kmh,
            message_en=f"Wind speed {wind_kmh:.0f} km/h ≥ Beaufort Force 6 — hazardous.",
            message_zh=f"风速 {wind_kmh:.0f} km/h 达到蒲福风级 6 级以上，存在危险。",
        ))
    if cape >= config.HIGH_CAPE_JKG:
        out.append(VetoTrigger(
            rule="high_cape_lightning", value=cape,
            message_en=f"CAPE {cape:.0f} J/kg — significant thunderstorm potential.",
            message_zh=f"CAPE {cape:.0f} J/kg，存在显著雷暴风险。",
        ))
    if visibility < config.LOW_VISIBILITY_M:
        out.append(VetoTrigger(
            rule="low_visibility", value=visibility,
            message_en=f"Visibility {visibility:.0f} m — whiteout / dense fog.",
            message_zh=f"能见度 {visibility:.0f} m，白毛风或浓雾。",
        ))
    if (terrain == "Slope" and orographic_dot >= config.OROGRAPHIC_DOT_THRESHOLD
            and ml_rain_prob >= 0.50):
        out.append(VetoTrigger(
            rule="orographic_lift_storm", value=orographic_dot,
            message_en="Wind impinging on windward slope with high rain probability — enhanced orographic precipitation.",
            message_zh="风向正对迎风坡，叠加高降雨概率，地形抬升强化降水。",
        ))
    if terrain == "Valley" and ml_rain_prob >= config.VALLEY_FLOOD_PROB:
        out.append(VetoTrigger(
            rule="valley_flash_flood", value=ml_rain_prob,
            message_en="Valley basin with very high rain probability — flash-flood risk.",
            message_zh="处于山谷盆地且降雨概率极高，存在山洪暴发风险。",
        ))
    return out


# ════════════════════════════════════════════════════════════════════════
# Top-level entry point — orchestrates P4.2 → P4.3 → P4.4 → P4.5 → P4.6
# ════════════════════════════════════════════════════════════════════════

def evaluate(
    *,
    lat: float,
    lon: float,
    elevation_m: float,
    terrain: str,
    weather: dict[str, Any],
    ml_rain_prob: float,
    slope_deg: float,
    aspect_deg: float,
    orographic_dot: float,
    activity: ActivityType = "general",
) -> RuleResult:
    """Apply the full Hybrid scoring + Veto cascade + D5 §3.7 pipeline."""
    result = RuleResult(activity=activity)
    log = result.inference_log

    log.append(InferenceStep(
        kind="info",
        text_en=f"Inference @ ({lat:.4f}, {lon:.4f})  elev={elevation_m:.0f} m  terrain={terrain}  activity={activity}",
        text_zh=f"推理位置 ({lat:.4f}, {lon:.4f})  海拔 {elevation_m:.0f} m  地形 {terrain}  活动类型 {activity}",
    ))
    log.append(InferenceStep(
        kind="ml",
        text_en=f"Engine A (Random Forest) — rain probability next hour = {ml_rain_prob:.1%}",
        text_zh=f"引擎 A（随机森林）下一小时降雨概率 = {ml_rain_prob:.1%}",
    ))

    # ── P4.3: Four hazard sub-scores ──
    humidity = weather.get("humidity_pct", 60.0)
    dew_dep  = weather.get("dew_point_depression",
                            weather.get("temperature_c", 25.0) - weather.get("dew_point_c",
                                weather.get("temperature_c", 25.0)))
    pres_dp  = weather.get("pressure_change_3h", 0.0)
    cloud    = weather.get("cloud_cover_pct", 50.0)
    cape     = weather.get("cape_jkg", 0.0)
    wind_kmh = weather.get("wind_speed_kmh", 0.0)

    subs = HazardSubscores(
        rainfall    = score_rainfall_risk(
            ml_rain_prob=ml_rain_prob, terrain=terrain, orographic_dot=orographic_dot,
            pressure_change_3h=pres_dp, humidity_pct=humidity),
        fog         = score_fog_risk(
            humidity_pct=humidity, dew_point_depression=dew_dep,
            cloud_cover_pct=cloud, terrain=terrain, elevation_m=elevation_m),
        wind_gust   = score_wind_gust_risk(
            wind_speed_kmh=wind_kmh, terrain=terrain,
            slope_deg=slope_deg, orographic_dot=orographic_dot),
        thunderstorm= score_thunderstorm_risk(
            cape_jkg=cape, pressure_change_3h=pres_dp, humidity_pct=humidity),
    )
    result.hazard_subscores = subs

    log.append(InferenceStep(
        kind="hazard",
        text_en=f"Sub-scores — Rainfall={subs.rainfall}  Fog={subs.fog}  Gust={subs.wind_gust}  Thunder={subs.thunderstorm}",
        text_zh=f"分项评分 — 降雨={subs.rainfall}  雾={subs.fog}  阵风={subs.wind_gust}  雷暴={subs.thunderstorm}",
    ))

    # ── D5 §3.7.2 Decision Table R1-R4 (informational, not score-changing) ──
    wind_into_slope = (terrain == "Slope" and orographic_dot >= 0.3)
    cloud_base_m   = weather.get("cloud_base_m")
    if cloud_base_m is None and cloud >= 90.0 and dew_dep <= 2.0:
        cloud_base_m = 600.0   # crude proxy when API doesn't provide cloud base

    result.decision_table_matches = apply_decision_table_3_7_2(
        macro_rain_prob=ml_rain_prob,
        humidity_pct=humidity,
        wind_into_slope=wind_into_slope,
        terrain=terrain,
        pressure_change_3h=pres_dp,
        cloud_base_m=cloud_base_m,
    )
    for m in result.decision_table_matches:
        log.append(InferenceStep(
            kind="table",
            text_en=f"D5 §3.7.2 {m.rule} fired — {m.conclusion_en}",
            text_zh=f"D5 §3.7.2 {m.rule} 触发 —— {m.conclusion_zh}",
        ))

    # ── Veto cascade (life-safety overrides) ──
    result.veto_triggers = _collect_veto_triggers(
        elevation_m=elevation_m, terrain=terrain, weather=weather,
        ml_rain_prob=ml_rain_prob, orographic_dot=orographic_dot,
    )
    if result.has_veto:
        for v in result.veto_triggers:
            log.append(InferenceStep(kind="veto", text_en=f"VETO: {v.message_en}",
                                      text_zh=f"否决触发：{v.message_zh}"))
        result.risk_score = 100
        result.risk_level = "Danger"
        result.advice_en, result.advice_zh = _veto_advice(result.veto_triggers)
        log.append(InferenceStep(kind="score",
            text_en="Final risk = 100 (Veto cascade; ML probability overridden).",
            text_zh="最终风险 = 100（一票否决；ML 概率被覆盖）。"))
        return result

    # ── P4.4 + P4.5: activity-weighted composite score ──
    composite = apply_activity_weighting(subs, activity)
    result.risk_score = composite
    result.risk_level = _bin_level(composite)
    log.append(InferenceStep(
        kind="activity",
        text_en=f"Activity={activity}: weighted composite score = {composite}.",
        text_zh=f"活动类型 {activity}：加权综合评分 = {composite}。",
    ))

    # ── P4.6: bilingual advice ──
    result.advice_en, result.advice_zh = _normal_advice(
        composite, terrain, ml_rain_prob, subs, activity)
    log.append(InferenceStep(kind="score",
        text_en=f"Final risk score = {composite} → {result.risk_level}.",
        text_zh=f"最终风险评分 = {composite} → {result.risk_level}。"))
    return result


# ════════════════════════════════════════════════════════════════════════
# P4.6 — Bilingual advice generation
# ════════════════════════════════════════════════════════════════════════

def _veto_advice(triggers: list[VetoTrigger]) -> tuple[str, str]:
    en = "DANGER — do not proceed. " + " ".join(t.message_en for t in triggers)
    zh = "危险 —— 请勿前往。" + " ".join(t.message_zh for t in triggers)
    return en, zh


def _normal_advice(score: int, terrain: str, ml_prob: float,
                   subs: HazardSubscores, activity: ActivityType) -> tuple[str, str]:
    # Pick the dominant hazard to mention specifically.
    by_score = sorted(
        [("Rainfall", "降雨", subs.rainfall),
         ("Fog",      "雾",   subs.fog),
         ("Wind gust","阵风", subs.wind_gust),
         ("Thunderstorm","雷暴", subs.thunderstorm)],
        key=lambda x: -x[2],
    )
    top_en, top_zh, top_score = by_score[0]

    if score >= 80:
        en = f"Danger ({top_en} dominant, {top_score}/100): cancel outdoor activity; seek shelter immediately."
        zh = f"危险（主要风险 {top_zh} {top_score}/100）：立即取消户外活动，寻找避难所。"
    elif score >= 55:
        en = (f"Warning ({top_en} dominant, {top_score}/100) in {terrain.lower()} terrain "
              f"for activity={activity}. Postpone non-essential travel.")
        zh = f"警告（主要风险 {top_zh} {top_score}/100）：{terrain}地形下 {activity} 活动，建议推迟非必要出行。"
    elif score >= 30:
        en = (f"Caution ({top_en} dominant, {top_score}/100): monitor weather closely; "
              f"carry appropriate gear (rain prob {ml_prob:.0%}).")
        zh = f"注意（主要风险 {top_zh} {top_score}/100）：密切关注天气，携带适当装备（降雨概率 {ml_prob:.0%}）。"
    else:
        en = "Safe: conditions favourable for outdoor activity. Stay aware."
        zh = "安全：当前条件适合户外活动，仍请保持警觉。"
    return en, zh
