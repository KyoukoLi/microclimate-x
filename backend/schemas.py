"""Pydantic request / response schemas — the contract between FE and BE."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TerrainType = Literal["Valley", "Slope", "Flat", "Peak", "Unknown"]
RiskLevel   = Literal["Safe", "Caution", "Warning", "Danger"]


class PredictionRequest(BaseModel):
    latitude:  float = Field(..., ge=-90.0,  le=90.0,  description="WGS84 latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS84 longitude")


class VetoTrigger(BaseModel):
    rule:    str
    value:   float | None
    message_en: str
    message_zh: str


class InferenceStep(BaseModel):
    """One line of the XAI (explainable AI) inference log."""
    kind: Literal["info", "ml", "rule", "veto", "score"]
    text_en: str
    text_zh: str


class PredictionResponse(BaseModel):
    latitude:  float
    longitude: float
    elevation_m: float
    terrain: TerrainType

    ml_rain_probability: float = Field(..., ge=0.0, le=1.0)
    risk_score: int = Field(..., ge=0, le=100)
    risk_level: RiskLevel

    veto_triggers: list[VetoTrigger]
    inference_log: list[InferenceStep]

    advice_en: str
    advice_zh: str

    cached:    bool = False
    cache_ttl: int  = 0
