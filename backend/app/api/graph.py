"""Trust Graph API endpoints — traversal, path finding, blast radius."""

import uuid

from fastapi import APIRouter, HTTPException, Query

from app.schemas.graph import (
    BlastRadiusResponse,
    BlastRadiusIdentity,
    GraphStatsResponse,
    PathResponse,
    TraverseResponse,
    TrustChainSchema,
    TrustChainStepSchema,
)
from app.services.graph_engine import graph_engine

router = APIRouter()


@router.get("/graph/traverse", response_model=TraverseResponse)
async def traverse_graph(
    start_identity_id: uuid.UUID = Query(...),
    max_depth: int = Query(default=10, ge=1, le=10),
):
    """Traverse trust graph from a starting identity, returning all reachable chains."""
    start_data = graph_engine.get_identity_data(start_identity_id)
    if not start_data:
        raise HTTPException(status_code=404, detail="Start identity not found in graph")

    chains = graph_engine.traverse(start_identity_id, max_depth=max_depth)

    chain_schemas = [
        TrustChainSchema(
            path=[
                TrustChainStepSchema(
                    identity_id=step.identity_id,
                    name=step.name,
                    type=step.type,
                    trust_type=step.trust_type,
                )
                for step in chain.path
            ],
            hop_count=chain.hop_count,
        )
        for chain in chains
    ]

    # Count unique reachable identities
    reachable_ids = set()
    for chain in chains:
        for step in chain.path[1:]:  # Skip start node
            reachable_ids.add(step.identity_id)

    return TraverseResponse(
        start_identity=TrustChainStepSchema(
            identity_id=start_identity_id,
            name=start_data["name"],
            type=start_data["type"],
        ),
        chains=chain_schemas,
        total_reachable_identities=len(reachable_ids),
        total_reachable_resources=0,  # Resources not in graph nodes
    )


@router.get("/graph/path", response_model=PathResponse)
async def find_path(
    source_identity_id: uuid.UUID = Query(...),
    target_identity_id: uuid.UUID = Query(...),
    max_depth: int = Query(default=10, ge=1, le=10),
):
    """Find all trust paths between two identities."""
    source_data = graph_engine.get_identity_data(source_identity_id)
    target_data = graph_engine.get_identity_data(target_identity_id)

    if not source_data:
        raise HTTPException(status_code=404, detail="Source identity not found in graph")
    if not target_data:
        raise HTTPException(status_code=404, detail="Target identity not found in graph")

    chains = graph_engine.find_path(source_identity_id, target_identity_id, max_depth=max_depth)

    path_schemas = [
        TrustChainSchema(
            path=[
                TrustChainStepSchema(
                    identity_id=step.identity_id,
                    name=step.name,
                    type=step.type,
                    trust_type=step.trust_type,
                )
                for step in chain.path
            ],
            hop_count=chain.hop_count,
        )
        for chain in chains
    ]

    return PathResponse(
        source=TrustChainStepSchema(
            identity_id=source_identity_id,
            name=source_data["name"],
            type=source_data["type"],
        ),
        target=TrustChainStepSchema(
            identity_id=target_identity_id,
            name=target_data["name"],
            type=target_data["type"],
        ),
        paths=path_schemas,
        total_paths=len(path_schemas),
    )


@router.get("/graph/blast-radius/{identity_id}", response_model=BlastRadiusResponse)
async def get_blast_radius(identity_id: uuid.UUID):
    """Get blast radius — all reachable identities from a starting identity."""
    identity_data = graph_engine.get_identity_data(identity_id)
    if not identity_data:
        raise HTTPException(status_code=404, detail="Identity not found in graph")

    blast = graph_engine.blast_radius(identity_id)

    return BlastRadiusResponse(
        identity_id=identity_id,
        identity_name=identity_data["name"],
        reachable_identities=[
            BlastRadiusIdentity(
                id=uuid.UUID(item["id"]) if isinstance(item["id"], str) else item["id"],
                name=item["name"],
                type=item["type"],
                risk_score=item.get("risk_score", 0),
            )
            for item in blast.reachable_identities
        ],
        reachable_resources=[],
        total_reachable_identities=blast.total_reachable_identities,
        total_reachable_resources=blast.total_reachable_resources,
    )


@router.get("/graph/full")
async def get_full_graph():
    """Get ALL nodes and edges for full graph visualization."""
    from app.database import async_session_factory
    from app.models import Identity, TrustRelationship
    from sqlalchemy import select

    async with async_session_factory() as session:
        # Get all identities
        result = await session.execute(select(Identity))
        identities = result.scalars().all()

        # Get all trust relationships
        result = await session.execute(select(TrustRelationship))
        relationships = result.scalars().all()

    nodes = [
        {
            "id": str(i.id),
            "name": i.name,
            "type": i.type,
            "source": i.source,
            "risk_score": i.risk_score,
            "last_used_at": i.last_used_at.isoformat() if i.last_used_at else None,
        }
        for i in identities
    ]

    edges = [
        {
            "id": str(r.id),
            "source": str(r.source_identity_id),
            "target": str(r.target_identity_id),
            "trust_type": r.trust_type,
        }
        for r in relationships
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
    }
    """Get graph statistics (node count, edge count, connected components)."""
    stats = graph_engine.get_stats()
    return GraphStatsResponse(**stats)


@router.get("/graph/stats", response_model=GraphStatsResponse)
async def get_graph_stats():
    """Get graph statistics (node count, edge count, connected components)."""
    stats = graph_engine.get_stats()
    return GraphStatsResponse(**stats)
