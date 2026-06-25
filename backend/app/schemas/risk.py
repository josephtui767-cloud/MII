"""Pydantic schemas for Risk scoring endpoints."""

from uuid import UUID

from pydantic import BaseModel


class RiskFactorDetail(BaseModel):
    factor: str
    points: int
    reason: str


class RiskScoreResponse(BaseModel):
    identity_id: UUID
    identity_name: str
    score: int
    factors: list[RiskFactorDetail]
    unevaluable_factors: list[str] = []


class RiskScoreListItem(BaseModel):
    identity_id: UUID
    identity_name: str
    identity_type: str
    source: str
    score: int
    factor_count: int


class RiskScoreListResponse(BaseModel):
    items: list[RiskScoreListItem]
    total: int
    page: int
    per_page: int
    pages: int


class RecalculateResponse(BaseModel):
    status: str
    identities_processed: int
    message: str
