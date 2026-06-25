"""Trust graph engine — builds and traverses the in-memory trust graph."""

import logging
import uuid
from dataclasses import dataclass, field

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session_factory
from app.models import Identity, TrustRelationship

logger = logging.getLogger(__name__)


@dataclass
class TrustChainStep:
    identity_id: uuid.UUID
    name: str
    type: str
    trust_type: str | None = None  # trust_type used to reach this node


@dataclass
class TrustChain:
    path: list[TrustChainStep]
    hop_count: int = 0


@dataclass
class BlastRadiusResult:
    start_identity_id: uuid.UUID
    reachable_identities: list[dict] = field(default_factory=list)
    reachable_resources: list[dict] = field(default_factory=list)
    total_reachable_identities: int = 0
    total_reachable_resources: int = 0


class GraphEngine:
    """In-memory directed graph for trust relationship traversal."""

    def __init__(self):
        self.graph = nx.DiGraph()
        self._identity_data: dict[uuid.UUID, dict] = {}

    async def rebuild(self):
        """Rebuild graph from current database state."""
        self.graph.clear()
        self._identity_data.clear()

        async with async_session_factory() as session:
            # Load all identities
            result = await session.execute(select(Identity))
            identities = result.scalars().all()

            for identity in identities:
                self.graph.add_node(identity.id)
                self._identity_data[identity.id] = {
                    "id": identity.id,
                    "name": identity.name,
                    "type": identity.type,
                    "source": identity.source,
                    "risk_score": identity.risk_score,
                }

            # Load all trust relationships
            result = await session.execute(select(TrustRelationship))
            relationships = result.scalars().all()

            for rel in relationships:
                self.graph.add_edge(
                    rel.source_identity_id,
                    rel.target_identity_id,
                    trust_type=rel.trust_type,
                    id=rel.id,
                )

        logger.info(
            f"Graph rebuilt: {self.graph.number_of_nodes()} nodes, "
            f"{self.graph.number_of_edges()} edges"
        )

    def traverse(self, start_id: uuid.UUID, max_depth: int = 10) -> list[TrustChain]:
        """BFS traversal returning all reachable chains from start_id."""
        if start_id not in self.graph:
            return []

        chains: list[TrustChain] = []
        visited = set()
        queue: list[tuple[uuid.UUID, list[TrustChainStep]]] = []

        start_data = self._identity_data.get(start_id, {})
        start_step = TrustChainStep(
            identity_id=start_id,
            name=start_data.get("name", "unknown"),
            type=start_data.get("type", "unknown"),
        )
        queue.append((start_id, [start_step]))
        visited.add(start_id)

        while queue:
            current_id, current_path = queue.pop(0)

            if len(current_path) - 1 >= max_depth:
                continue

            for neighbor in self.graph.successors(current_id):
                if neighbor in visited:
                    continue
                visited.add(neighbor)

                edge_data = self.graph.edges[current_id, neighbor]
                neighbor_data = self._identity_data.get(neighbor, {})

                step = TrustChainStep(
                    identity_id=neighbor,
                    name=neighbor_data.get("name", "unknown"),
                    type=neighbor_data.get("type", "unknown"),
                    trust_type=edge_data.get("trust_type"),
                )
                new_path = current_path + [step]
                chains.append(TrustChain(path=new_path, hop_count=len(new_path) - 1))
                queue.append((neighbor, new_path))

        return chains

    def find_path(self, source_id: uuid.UUID, target_id: uuid.UUID, max_depth: int = 10) -> list[TrustChain]:
        """Find all simple paths between source and target (max depth)."""
        if source_id not in self.graph or target_id not in self.graph:
            return []

        chains: list[TrustChain] = []
        try:
            paths = nx.all_simple_paths(self.graph, source_id, target_id, cutoff=max_depth)
            for path_nodes in paths:
                steps: list[TrustChainStep] = []
                for i, node_id in enumerate(path_nodes):
                    node_data = self._identity_data.get(node_id, {})
                    trust_type = None
                    if i > 0:
                        edge_data = self.graph.edges[path_nodes[i - 1], node_id]
                        trust_type = edge_data.get("trust_type")
                    steps.append(TrustChainStep(
                        identity_id=node_id,
                        name=node_data.get("name", "unknown"),
                        type=node_data.get("type", "unknown"),
                        trust_type=trust_type,
                    ))
                chains.append(TrustChain(path=steps, hop_count=len(steps) - 1))
        except nx.NetworkXError:
            pass

        return chains

    def blast_radius(self, identity_id: uuid.UUID) -> BlastRadiusResult:
        """Calculate all reachable identities from a starting identity."""
        result = BlastRadiusResult(start_identity_id=identity_id)

        if identity_id not in self.graph:
            return result

        reachable = nx.descendants(self.graph, identity_id)

        for node_id in reachable:
            data = self._identity_data.get(node_id, {})
            result.reachable_identities.append({
                "id": str(node_id),
                "name": data.get("name", "unknown"),
                "type": data.get("type", "unknown"),
                "risk_score": data.get("risk_score", 0),
            })

        result.total_reachable_identities = len(result.reachable_identities)
        return result

    def get_stats(self) -> dict:
        """Return graph statistics."""
        return {
            "node_count": self.graph.number_of_nodes(),
            "edge_count": self.graph.number_of_edges(),
            "connected_components": nx.number_weakly_connected_components(self.graph),
        }

    def get_identity_data(self, identity_id: uuid.UUID) -> dict | None:
        """Get cached identity data for a node."""
        return self._identity_data.get(identity_id)


# Singleton instance
graph_engine = GraphEngine()
