"""Pydantic request / response schemas — the contract between FE and BE."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TerrainType = Literal["Valley", "Slope", "Flat", "Peak", "Unknown"]
RiskLevel   = Literal["Safe", "Caution", "Warning", "Danger"]
ActivityType = Literal["hiker", "driver", "construction", "general"]


class PredictionRequest(BaseModel):
    latitude:  float = Field(..., ge=-90.0,  le=90.0,  description="WGS84 latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS84 longitude")
    activity:  ActivityType = "general"


class VetoTrigger(BaseModel):
    rule:    str
    value:   float | None
    message_en: str
    message_zh: str


class InferenceStep(BaseModel):
    """One line of the XAI (explainable AI) inference log."""
    kind: Literal["info", "ml", "rule", "veto", "score", "hazard", "table", "activity"]
    text_en: str
    text_zh: str


class HazardSubscores(BaseModel):
    """Per-category risk score 0-100. Matches the four hazard types
    enumerated in the D5 proposal §3.7 (P4.3)."""
    rainfall:     int = Field(..., ge=0, le=100)
    fog:          int = Field(..., ge=0, le=100)
    wind_gust:    int = Field(..., ge=0, le=100)
    thunderstorm: int = Field(..., ge=0, le=100)


class DecisionTableMatch(BaseModel):
    """A row of D5 §3.7.2 / Table 4.2 that has fired for this request."""
    rule:           str           # 'R1' | 'R2' | 'R3' | 'R4'
    description:    str
    conclusion_en:  str
    conclusion_zh:  str


class PredictionResponse(BaseModel):
    latitude:  float
    longitude: float
    elevation_m: float
    terrain: TerrainType

    ml_rain_probability: float = Field(..., ge=0.0, le=1.0)

    hazard_subscores: HazardSubscores
    decision_table_matches: list[DecisionTableMatch]
    activity: ActivityType

    risk_score: int = Field(..., ge=0, le=100)
    risk_level: RiskLevel

    veto_triggers: list[VetoTrigger]
    inference_log: list[InferenceStep]

    advice_en: str
    advice_zh: str

    cached:    bool = False
    cache_ttl: int  = 0
