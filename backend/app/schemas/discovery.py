"""Pydantic schemas for Discovery endpoints."""

from datetime import datetime

from pydantic import BaseModel


class DiscoveryRunResponse(BaseModel):
    status: str
    message: str
    started_at: datetime | None = None


class DiscoveryStatusResponse(BaseModel):
    status: str  # idle, running, completed, failed
    last_run_at: datetime | None = None
    last_duration_seconds: float | None = None
    identities_discovered: int = 0
    trust_relationships_discovered: int = 0
    resources_discovered: int = 0
    errors: list[str] = []
