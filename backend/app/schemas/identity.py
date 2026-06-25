"""Pydantic schemas for Identity endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RiskFactorSchema(BaseModel):
    factor: str
    points: int
    reason: str


class TrustedBySchema(BaseModel):
    id: UUID
    name: str
    type: str
    trust_type: str


class CanAccessSchema(BaseModel):
    id: UUID
    name: str
    resource_type: str
    access_type: str
    classification: str | None = None


class IdentityResponse(BaseModel):
    id: UUID
    name: str
    arn: str | None = None
    type: str
    source: str
    owner: str | None = None
    account_id: str | None = None
    last_used_at: datetime | None = None
    risk_score: int = 0
    risk_factors: list[RiskFactorSchema] = []
    created_at: datetime

    class Config:
        from_attributes = True


class IdentityDetailResponse(BaseModel):
    id: UUID
    name: str
    arn: str | None = None
    type: str
    source: str
    owner: str | None = None
    account_id: str | None = None
    last_used_at: datetime | None = None
    is_resolved: bool = True
    risk_score: int = 0
    risk_factors: list[RiskFactorSchema] = []
    trusted_by: list[TrustedBySchema] = []
    can_access: list[CanAccessSchema] = []
    created_at: datetime

    class Config:
        from_attributes = True


class IdentityListResponse(BaseModel):
    items: list[IdentityResponse]
    total: int
    page: int
    per_page: int
    pages: int


class IdentityFilterParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=25, ge=1, le=100)
    type: str | None = None
    source: str | None = None
    min_risk_score: int | None = Field(default=None, ge=0, le=100)
    has_admin: bool | None = None
    has_production_access: bool | None = None
    unused_days: int | None = Field(default=None, ge=1)
    trusted_by_gitlab: bool | None = None
    cross_account: bool | None = None
    sort_by: str = "risk_score"
    sort_order: str = "desc"
