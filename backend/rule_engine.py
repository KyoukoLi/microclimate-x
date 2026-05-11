"""
Topographic Rule-Based Expert System — Engine B of the hybrid architecture.

Workflow per request:
    1. Apply Veto rules. If ANY fires → risk = 100, status = "Danger",
       ML probability is overridden. This is the safety-critical layer.
    2. If no Veto fires → start from a base score and add penalty terms.
    3. Cap final score in [0, 100] and bin into Safe / Caution / Warning / Danger.
    4. Generate bilingual actionable advice.

Every threshold lives in `backend/config.py` with its academic citation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import config
from .schemas import InferenceStep, RiskLevel, VetoTrigger


@dataclass
class RuleResult:
    risk_score: int = 0
    risk_level: RiskLevel = "Safe"
    veto_triggers: list[VetoTrigger] = field(default_factory=list)
    inference_log: list[InferenceStep] = field(default_factory=list)
    advice_en: str = ""
    advice_zh: str = ""

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
) -> RuleResult:
    """Apply the full Hybrid scoring + Veto cascade."""
    result = RuleResult()
    log = result.inference_log

    log.append(InferenceStep(
        kind="info",
        text_en=f"Inference @ ({lat:.4f}, {lon:.4f})  elev={elevation_m:.0f} m  terrain={terrain}",
        text_zh=f"推理位置 ({lat:.4f}, {lon:.4f})  海拔 {elevation_m:.0f} m  地形 {terrain}",
    ))

    log.append(InferenceStep(
        kind="ml",
        text_en=f"Engine A (Random Forest) — rain probability next hour = {ml_rain_prob:.1%}",
        text_zh=f"引擎 A（随机森林）下一小时降雨概率 = {ml_rain_prob:.1%}",
    ))

    # ─────────────────────────────────────────────────────────────
    # Veto rules (one-vote rejection)
    # ─────────────────────────────────────────────────────────────
    temp_c    = weather.get("temperature_c", 25.0)
    wind_kmh  = weather.get("wind_speed_kmh", 0.0)
    cape      = weather.get("cape_jkg", 0.0)
    visibility = weather.get("visibility_m", 10000.0)

    if elevation_m > config.ALTITUDE_HYPOXIA_M:
        result.veto_triggers.append(VetoTrigger(
            rule="altitude_hypoxia",
            value=elevation_m,
            message_en=f"Altitude {elevation_m:.0f} m exceeds {config.ALTITUDE_HYPOXIA_M:.0f} m — severe hypoxia risk.",
            message_zh=f"海拔 {elevation_m:.0f} m 超过 {config.ALTITUDE_HYPOXIA_M:.0f} m，存在严重缺氧风险。",
        ))

    if temp_c <= config.EXTREME_COLD_C:
        result.veto_triggers.append(VetoTrigger(
            rule="extreme_cold",
            value=temp_c,
            message_en=f"Temperature {temp_c:.1f}°C — frostbite risk per UIAA guidance.",
            message_zh=f"温度 {temp_c:.1f}°C，UIAA 指南判定为冻伤风险。",
        ))

    if wind_kmh >= config.GALE_WIND_KMH:
        result.veto_triggers.append(VetoTrigger(
            rule="gale_wind",
            value=wind_kmh,
            message_en=f"Wind speed {wind_kmh:.0f} km/h ≥ Beaufort Force 6 — hazardous.",
            message_zh=f"风速 {wind_kmh:.0f} km/h 达到蒲福风级 6 级以上，存在危险。",
        ))

    if cape >= config.HIGH_CAPE_JKG:
        result.veto_triggers.append(VetoTrigger(
            rule="high_cape_lightning",
            value=cape,
            message_en=f"CAPE {cape:.0f} J/kg — significant thunderstorm potential.",
            message_zh=f"CAPE {cape:.0f} J/kg，存在显著雷暴风险。",
        ))

    if visibility < config.LOW_VISIBILITY_M:
        result.veto_triggers.append(VetoTrigger(
            rule="low_visibility",
            value=visibility,
            message_en=f"Visibility {visibility:.0f} m — whiteout / dense fog.",
            message_zh=f"能见度 {visibility:.0f} m，白毛风或浓雾。",
        ))

    if (
        terrain == "Slope"
        and orographic_dot >= config.OROGRAPHIC_DOT_THRESHOLD
        and ml_rain_prob >= 0.50
    ):
        result.veto_triggers.append(VetoTrigger(
            rule="orographic_lift_storm",
            value=orographic_dot,
            message_en="Wind impinging on windward slope with high rain probability — enhanced orographic precipitation.",
            message_zh="风向正对迎风坡，叠加高降雨概率，地形抬升强化降水。",
        ))

    if terrain == "Valley" and ml_rain_prob >= config.VALLEY_FLOOD_PROB:
        result.veto_triggers.append(VetoTrigger(
            rule="valley_flash_flood",
            value=ml_rain_prob,
            message_en="Valley basin with very high rain probability — flash-flood risk.",
            message_zh="处于山谷盆地且降雨概率极高，存在山洪暴发风险。",
        ))

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

    # ─────────────────────────────────────────────────────────────
    # Additive scoring (only when no Veto fired)
    # ─────────────────────────────────────────────────────────────
    score = int(round(ml_rain_prob * 40))  # base from ML
    log.append(InferenceStep(kind="rule",
        text_en=f"+{score} from ML rain probability baseline.",
        text_zh=f"+{score} 来自 ML 降雨概率基础分。"))

    if ml_rain_prob >= 0.70:
        score += config.PENALTY["ml_high_rain_prob"]
        log.append(InferenceStep(kind="rule",
            text_en=f"+{config.PENALTY['ml_high_rain_prob']} ML rain probability ≥ 70 %.",
            text_zh=f"+{config.PENALTY['ml_high_rain_prob']} ML 降雨概率 ≥ 70%。"))
    elif ml_rain_prob >= 0.40:
        score += config.PENALTY["ml_mid_rain_prob"]
        log.append(InferenceStep(kind="rule",
            text_en=f"+{config.PENALTY['ml_mid_rain_prob']} ML rain probability 40-70 %.",
            text_zh=f"+{config.PENALTY['ml_mid_rain_prob']} ML 降雨概率 40-70%。"))

    if terrain == "Valley":
        score += config.PENALTY["valley_floor"]
        log.append(InferenceStep(kind="rule",
            text_en=f"+{config.PENALTY['valley_floor']} Valley terrain (water-collection risk).",
            text_zh=f"+{config.PENALTY['valley_floor']} 山谷地形（汇水风险）。"))
    elif terrain == "Slope":
        score += config.PENALTY["windward_slope"] if orographic_dot > 0.3 else 0
        if orographic_dot > 0.3:
            log.append(InferenceStep(kind="rule",
                text_en=f"+{config.PENALTY['windward_slope']} Windward slope alignment.",
                text_zh=f"+{config.PENALTY['windward_slope']} 迎风坡朝向。"))
        if orographic_dot >= 0.5:
            score += config.PENALTY["orographic_lift"]
            log.append(InferenceStep(kind="rule",
                text_en=f"+{config.PENALTY['orographic_lift']} Orographic lift index high.",
                text_zh=f"+{config.PENALTY['orographic_lift']} 地形抬升指数偏高。"))

    if 2500.0 <= elevation_m < config.ALTITUDE_HYPOXIA_M:
        score += config.PENALTY["altitude_high"]
        log.append(InferenceStep(kind="rule",
            text_en=f"+{config.PENALTY['altitude_high']} Sub-hypoxia altitude band (2500-3500 m).",
            text_zh=f"+{config.PENALTY['altitude_high']} 亚缺氧海拔带 (2500-3500 m)。"))

    if 25.0 <= wind_kmh < config.GALE_WIND_KMH:
        score += config.PENALTY["wind_strong"]
        log.append(InferenceStep(kind="rule",
            text_en=f"+{config.PENALTY['wind_strong']} Strong wind 25-40 km/h.",
            text_zh=f"+{config.PENALTY['wind_strong']} 强风 25-40 km/h。"))

    score = max(0, min(100, score))
    result.risk_score = score
    result.risk_level = _bin_level(score)
    result.advice_en, result.advice_zh = _normal_advice(score, terrain, ml_rain_prob)
    log.append(InferenceStep(kind="score",
        text_en=f"Final risk score = {score} → {result.risk_level}.",
        text_zh=f"最终风险评分 = {score} → {result.risk_level}。"))
    return result


# ────────────────────────────────────────────────────────────────────────
# Advice generation (bilingual)
# ────────────────────────────────────────────────────────────────────────

def _veto_advice(triggers: list[VetoTrigger]) -> tuple[str, str]:
    en = "DANGER — do not proceed. " + " ".join(t.message_en for t in triggers)
    zh = "危险 —— 请勿前往。" + " ".join(t.message_zh for t in triggers)
    return en, zh


def _normal_advice(score: int, terrain: str, ml_prob: float) -> tuple[str, str]:
    if score >= 80:
        en = "Danger: cancel outdoor activity; seek shelter immediately."
        zh = "危险等级：建议立即取消户外活动，寻找避难所。"
    elif score >= 55:
        en = (f"Warning: high microclimate risk in {terrain.lower()} terrain "
              f"(rain prob {ml_prob:.0%}). Postpone non-essential travel.")
        zh = f"警告：当前{terrain}地形微气候风险较高（降雨概率 {ml_prob:.0%}），建议推迟非必要出行。"
    elif score >= 30:
        en = (f"Caution: monitor weather closely; carry rain gear "
              f"(rain prob {ml_prob:.0%}).")
        zh = f"注意：请密切关注天气，建议携带雨具（降雨概率 {ml_prob:.0%}）。"
    else:
        en = "Safe: conditions favourable for outdoor activity. Stay aware."
        zh = "安全：当前条件适合户外活动，仍请保持警觉。"
    return en, zh
