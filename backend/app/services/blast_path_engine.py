"""Blast Path Simulation Engine — simulates attack paths from a compromised identity."""

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.database import async_session_factory
from app.models import Identity, IdentityAccess, Resource, TrustRelationship
from app.services.graph_engine import graph_engine

logger = logging.getLogger(__name__)


@dataclass
class AttackStep:
    step_number: int
    action: str
    from_identity_id: str
    from_identity_name: str
    to_identity_id: str
    to_identity_name: str
    trust_type: str
    risk_level: str  # critical, high, medium, low
    description: str


@dataclass
class CompromisedResource:
    resource_id: str
    resource_name: str
    resource_type: str
    access_type: str
    classification: str
    reached_via: str


@dataclass
class BlastPathResult:
    start_identity_id: str
    start_identity_name: str
    start_identity_type: str
    scenario: str
    attack_steps: list[AttackStep] = field(default_factory=list)
    compromised_identities: list = field(default_factory=list)
    compromised_resources: list[CompromisedResource] = field(default_factory=list)
    total_blast_radius: int = 0
    severity: str = "low"
    narrative: str = ""


class BlastPathEngine:
    """Simulates attack paths from a compromised identity through trust chains."""

    async def simulate(self, identity_id: uuid.UUID) -> dict:
        """Simulate full blast path from a compromised identity."""
        async with async_session_factory() as session:
            # Get the starting identity
            stmt = select(Identity).where(Identity.id == identity_id)
            result = await session.execute(stmt)
            identity = result.scalar_one_or_none()

            if not identity:
                return {"error": f"Identity {identity_id} not found"}

            blast_result = BlastPathResult(
                start_identity_id=str(identity.id),
                start_identity_name=identity.name,
                start_identity_type=identity.type,
                scenario=self._generate_scenario(identity),
            )

            # Step 1: Find all directly reachable identities via trust
            await self._trace_trust_chains(session, identity, blast_result)

            # Step 2: Find all resources accessible from compromised identities
            await self._find_accessible_resources(session, blast_result)

            # Step 3: Calculate severity
            blast_result.total_blast_radius = (
                len(blast_result.compromised_identities) +
                len(blast_result.compromised_resources)
            )
            blast_result.severity = self._calculate_severity(blast_result)

            # Step 4: Generate narrative
            blast_result.narrative = self._generate_narrative(blast_result)

            return self._result_to_dict(blast_result)

    async def simulate_from_gitlab(self) -> dict:
        """Simulate attack starting from GitLab CI/CD compromise."""
        async with async_session_factory() as session:
            # Find GitLab OIDC identities
            stmt = select(Identity).where(Identity.type == "GitLab_Runner")
            result = await session.execute(stmt)
            gitlab_identities = result.scalars().all()

            if not gitlab_identities:
                return {"error": "No GitLab identities found. Run discovery first."}

            # Pick the one with the most outgoing trust relationships
            best_identity = gitlab_identities[0]
            best_count = 0

            for identity in gitlab_identities:
                count_stmt = select(func.count()).select_from(TrustRelationship).where(
                    TrustRelationship.source_identity_id == identity.id
                )
                count_result = await session.execute(count_stmt)
                count = count_result.scalar() or 0
                if count > best_count:
                    best_count = count
                    best_identity = identity

            return await self.simulate(best_identity.id)

    async def _trace_trust_chains(self, session, start_identity: Identity, result: BlastPathResult):
        """Trace all trust chains from the starting identity."""
        # Get outgoing trust relationships (what can this identity assume)
        stmt = select(TrustRelationship).where(
            TrustRelationship.source_identity_id == start_identity.id
        ).options(selectinload(TrustRelationship.target_identity))
        trust_result = await session.execute(stmt)
        outgoing = trust_result.scalars().all()

        visited = {start_identity.id}
        queue = [(start_identity, outgoing, 1)]

        while queue:
            current_identity, relationships, depth = queue.pop(0)

            if depth > 10:  # Max depth
                break

            for rel in relationships:
                target = rel.target_identity
                if not target or target.id in visited:
                    continue

                visited.add(target.id)

                # Create attack step
                step = AttackStep(
                    step_number=len(result.attack_steps) + 1,
                    action=self._trust_type_to_action(rel.trust_type),
                    from_identity_id=str(current_identity.id),
                    from_identity_name=current_identity.name,
                    to_identity_id=str(target.id),
                    to_identity_name=target.name,
                    trust_type=rel.trust_type,
                    risk_level=self._step_risk_level(target),
                    description=self._step_description(current_identity, target, rel.trust_type),
                )
                result.attack_steps.append(step)

                # Add to compromised list
                result.compromised_identities.append({
                    "id": str(target.id),
                    "name": target.name,
                    "type": target.type,
                    "risk_score": target.risk_score,
                    "hop_count": depth,
                    "via_trust_type": rel.trust_type,
                })

                # Get next level relationships
                next_stmt = select(TrustRelationship).where(
                    TrustRelationship.source_identity_id == target.id
                ).options(selectinload(TrustRelationship.target_identity))
                next_result = await session.execute(next_stmt)
                next_rels = next_result.scalars().all()

                if next_rels:
                    queue.append((target, next_rels, depth + 1))

    async def _find_accessible_resources(self, session, result: BlastPathResult):
        """Find all resources accessible from compromised identities."""
        all_identity_ids = [result.start_identity_id] + [
            i["id"] for i in result.compromised_identities
        ]

        for identity_id in all_identity_ids:
            stmt = (
                select(IdentityAccess)
                .where(IdentityAccess.identity_id == uuid.UUID(identity_id))
                .options(selectinload(IdentityAccess.resource))
            )
            access_result = await session.execute(stmt)
            access_records = access_result.scalars().all()

            for record in access_records:
                if not record.resource:
                    continue
                # Avoid duplicates
                existing_ids = {r.resource_id for r in result.compromised_resources}
                if str(record.resource.id) not in existing_ids:
                    # Find which identity gave access
                    identity_name = result.start_identity_name
                    for ci in result.compromised_identities:
                        if ci["id"] == identity_id:
                            identity_name = ci["name"]
                            break

                    result.compromised_resources.append(CompromisedResource(
                        resource_id=str(record.resource.id),
                        resource_name=record.resource.name,
                        resource_type=record.resource.resource_type,
                        access_type=record.access_type,
                        classification=record.resource.classification or "unclassified",
                        reached_via=identity_name,
                    ))

    def _generate_scenario(self, identity: Identity) -> str:
        """Generate a realistic attack scenario description."""
        if identity.type == "GitLab_Runner":
            return (
                "Attacker gains access to a GitLab CI/CD pipeline "
                "(via compromised credentials, malicious MR, or supply chain attack). "
                "They can now assume any AWS role trusted by this GitLab OIDC identity."
            )
        elif "deploy" in identity.name.lower() or "ci" in identity.name.lower():
            return (
                f"Attacker compromises the '{identity.name}' role credentials "
                f"(via leaked temporary credentials, SSRF, or metadata endpoint access). "
                f"They can now use this role's permissions and assume any roles it trusts."
            )
        else:
            return (
                f"Attacker gains access to '{identity.name}' "
                f"(via credential theft, privilege escalation, or misconfigurated access). "
                f"They can now access all resources this identity has permissions for."
            )

    def _generate_narrative(self, result: BlastPathResult) -> str:
        """Generate a human-readable narrative of the attack path."""
        parts = [f"Starting from '{result.start_identity_name}':"]

        if result.attack_steps:
            parts.append(f"\n\nAttack Chain ({len(result.attack_steps)} hops):")
            for step in result.attack_steps[:5]:
                parts.append(f"  Step {step.step_number}: {step.description}")

        if result.compromised_resources:
            prod_resources = [r for r in result.compromised_resources if r.classification == "production"]
            admin_resources = [r for r in result.compromised_resources if r.access_type == "Admin"]

            parts.append(f"\n\nImpact Summary:")
            parts.append(f"  - {len(result.compromised_identities)} identities compromised")
            parts.append(f"  - {len(result.compromised_resources)} resources accessible")
            if prod_resources:
                parts.append(f"  - {len(prod_resources)} PRODUCTION resources at risk")
            if admin_resources:
                parts.append(f"  - {len(admin_resources)} resources with ADMIN access")

        return "\n".join(parts)

    @staticmethod
    def _trust_type_to_action(trust_type: str) -> str:
        actions = {
            "OIDC_Federation": "Assume role via OIDC token",
            "AssumeRole": "Assume role via sts:AssumeRole",
            "Cross_Account_Trust": "Assume role cross-account",
            "Pipeline_Assume": "Assume role from pipeline",
        }
        return actions.get(trust_type, f"Trust via {trust_type}")

    @staticmethod
    def _step_risk_level(target: Identity) -> str:
        if target.risk_score >= 60:
            return "critical"
        elif target.risk_score >= 35:
            return "high"
        elif target.risk_score >= 15:
            return "medium"
        return "low"

    @staticmethod
    def _step_description(source: Identity, target: Identity, trust_type: str) -> str:
        type_desc = {
            "OIDC_Federation": "assumes via OIDC federation",
            "AssumeRole": "assumes role",
            "Cross_Account_Trust": "crosses account boundary to assume",
            "Pipeline_Assume": "pipeline assumes",
        }
        action = type_desc.get(trust_type, "trusts")
        return f"'{source.name}' {action} '{target.name}'"

    @staticmethod
    def _calculate_severity(result: BlastPathResult) -> str:
        prod_resources = [r for r in result.compromised_resources if r.classification == "production"]
        admin_access = [r for r in result.compromised_resources if r.access_type == "Admin"]
        high_risk_identities = [i for i in result.compromised_identities if i.get("risk_score", 0) >= 35]

        if admin_access or len(prod_resources) > 3 or len(high_risk_identities) > 2:
            return "critical"
        elif prod_resources or len(result.compromised_identities) > 5:
            return "high"
        elif result.compromised_identities:
            return "medium"
        return "low"

    @staticmethod
    def _result_to_dict(result: BlastPathResult) -> dict:
        return {
            "start_identity": {
                "id": result.start_identity_id,
                "name": result.start_identity_name,
                "type": result.start_identity_type,
            },
            "scenario": result.scenario,
            "severity": result.severity,
            "narrative": result.narrative,
            "attack_steps": [
                {
                    "step_number": s.step_number,
                    "action": s.action,
                    "from_identity": {"id": s.from_identity_id, "name": s.from_identity_name},
                    "to_identity": {"id": s.to_identity_id, "name": s.to_identity_name},
                    "trust_type": s.trust_type,
                    "risk_level": s.risk_level,
                    "description": s.description,
                }
                for s in result.attack_steps
            ],
            "compromised_identities": result.compromised_identities,
            "compromised_resources": [
                {
                    "id": r.resource_id,
                    "name": r.resource_name,
                    "resource_type": r.resource_type,
                    "access_type": r.access_type,
                    "classification": r.classification,
                    "reached_via": r.reached_via,
                }
                for r in result.compromised_resources
            ],
            "total_blast_radius": result.total_blast_radius,
            "summary": {
                "identities_compromised": len(result.compromised_identities),
                "resources_accessible": len(result.compromised_resources),
                "production_resources": sum(
                    1 for r in result.compromised_resources if r.classification == "production"
                ),
                "admin_access_count": sum(
                    1 for r in result.compromised_resources if r.access_type == "Admin"
                ),
                "max_hop_count": max((i.get("hop_count", 0) for i in result.compromised_identities), default=0),
            },
        }
