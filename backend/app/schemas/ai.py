"""Pydantic schemas for AI Advisor endpoints."""

from uuid import UUID

from pydantic import BaseModel

from app.schemas.risk import RiskFactorDetail


class ExplainRiskRequest(BaseModel):
    identity_id: UUID


class ExplainRiskResponse(BaseModel):
    identity_id: UUID
    identity_name: str
    explanation: str
    risk_score: int
    risk_factors: list[RiskFactorDetail]


class ExplainPathRequest(BaseModel):
    source_identity_id: UUID
    target_identity_id: UUID


class ExplainPathResponse(BaseModel):
    source_name: str
    target_name: str
    explanation: str
    path_exists: bool
    hop_count: int | None = None


class BlastRadiusExplainRequest(BaseModel):
    identity_id: UUID


class BlastRadiusExplainResponse(BaseModel):
    identity_id: UUID
    identity_name: str
    explanation: str
    total_reachable: int
