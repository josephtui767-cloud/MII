"""Pydantic schemas for Trust Graph endpoints."""

from uuid import UUID

from pydantic import BaseModel, Field


class TrustChainStepSchema(BaseModel):
    identity_id: UUID
    name: str
    type: str
    trust_type: str | None = None


class ReachableResourceSchema(BaseModel):
    id: UUID
    name: str
    resource_type: str
    access_type: str


class TrustChainSchema(BaseModel):
    path: list[TrustChainStepSchema]
    hop_count: int
    reachable_resources: list[ReachableResourceSchema] = []


class TraverseResponse(BaseModel):
    start_identity: TrustChainStepSchema
    chains: list[TrustChainSchema]
    total_reachable_identities: int
    total_reachable_resources: int


class PathResponse(BaseModel):
    source: TrustChainStepSchema
    target: TrustChainStepSchema
    paths: list[TrustChainSchema]
    total_paths: int


class BlastRadiusIdentity(BaseModel):
    id: UUID
    name: str
    type: str
    risk_score: int = 0


class BlastRadiusResource(BaseModel):
    id: UUID
    name: str
    resource_type: str
    access_type: str


class BlastRadiusResponse(BaseModel):
    identity_id: UUID
    identity_name: str
    reachable_identities: list[BlastRadiusIdentity]
    reachable_resources: list[BlastRadiusResource]
    total_reachable_identities: int
    total_reachable_resources: int


class GraphStatsResponse(BaseModel):
    node_count: int
    edge_count: int
    connected_components: int


class TraverseParams(BaseModel):
    start_identity_id: UUID
    max_depth: int = Field(default=10, ge=1, le=10)
    direction: str = Field(default="outgoing", pattern="^(outgoing|incoming)$")


class PathParams(BaseModel):
    source_identity_id: UUID
    target_identity_id: UUID
    max_depth: int = Field(default=10, ge=1, le=10)
