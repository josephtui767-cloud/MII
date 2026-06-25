"""Trust Debt Engine — calculates trust debt score and identifies accumulated trust debt."""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.database import async_session_factory
from app.models import Identity, IdentityAccess, Resource, TrustRelationship

logger = logging.getLogger(__name__)

# Debt weights
DEBT_UNUSED_OIDC_FEDERATION = 40
DEBT_ADMIN_ON_OIDC_ROLE = 50
DEBT_NO_BRANCH_RESTRICTION = 30
DEBT_UNUSED_TRUST_RELATIONSHIP = 20
DEBT_STALE_IDENTITY_WITH_TRUST = 25
DEBT_CROSS_ACCOUNT_NO_EXTERNAL_ID = 35
DEBT_WILDCARD_RESOURCE_ACCESS = 15
DEBT_OVERPRIVILEGED_SERVICE_ROLE = 10


@dataclass
class TrustDebtItem:
    category: str
    description: str
    points: int
    affected_identity_id: str
    affected_identity_name: str
    recommendation: str
    age_days: int = 0


@dataclass
class TrustDebtResult:
    total_debt_score: int = 0
    max_possible_score: int = 0
    debt_percentage: float = 0.0
    debt_grade: str = "A"
    trend: str = "stable"  # increasing, decreasing, stable
    debt_items: list[TrustDebtItem] = field(default_factory=list)
    category_breakdown: dict = field(default_factory=dict)
    top_contributors: list = field(default_factory=list)


class TrustDebtEngine:
    """Calculates trust debt — accumulated unnecessary or risky trust relationships."""

    async def calculate_trust_debt(self) -> dict:
        """Calculate overall trust debt score and breakdown."""
        result = TrustDebtResult()

        async with async_session_factory() as session:
            # Load all identities
            stmt = select(Identity)
            identity_result = await session.execute(stmt)
            identities = identity_result.scalars().all()

            # Load all trust relationships
            trust_stmt = select(TrustRelationship)
            trust_result = await session.execute(trust_stmt)
            trust_relationships = trust_result.scalars().all()

            # Calculate debt items
            await self._check_unused_oidc_federations(session, identities, trust_relationships, result)
            await self._check_admin_on_oidc_roles(session, identities, result)
            await self._check_no_branch_restrictions(session, identities, result)
            await self._check_unused_trust_relationships(session, identities, trust_relationships, result)
            await self._check_stale_identities_with_trust(session, identities, trust_relationships, result)
            await self._check_overprivileged_access(session, identities, result)

        # Calculate totals
        result.total_debt_score = sum(item.points for item in result.debt_items)
        result.max_possible_score = len(identities) * 50  # Theoretical max
        result.debt_percentage = round(
            (result.total_debt_score / max(result.max_possible_score, 1)) * 100, 1
        )

        # Grade (like credit score)
        if result.total_debt_score == 0:
            result.debt_grade = "A"
        elif result.total_debt_score <= 50:
            result.debt_grade = "B"
        elif result.total_debt_score <= 150:
            result.debt_grade = "C"
        elif result.total_debt_score <= 300:
            result.debt_grade = "D"
        else:
            result.debt_grade = "F"

        # Category breakdown
        categories: dict[str, int] = {}
        for item in result.debt_items:
            categories[item.category] = categories.get(item.category, 0) + item.points
        result.category_breakdown = categories

        # Top contributors (top 5 identities by debt points)
        identity_debt: dict[str, dict] = {}
        for item in result.debt_items:
            key = item.affected_identity_id
            if key not in identity_debt:
                identity_debt[key] = {
                    "id": item.affected_identity_id,
                    "name": item.affected_identity_name,
                    "total_points": 0,
                    "issues": [],
                }
            identity_debt[key]["total_points"] += item.points
            identity_debt[key]["issues"].append(item.category)

        result.top_contributors = sorted(
            identity_debt.values(), key=lambda x: x["total_points"], reverse=True
        )[:5]

        return self._result_to_dict(result)

    async def _check_unused_oidc_federations(self, session, identities, trust_relationships, result):
        """Debt: OIDC federations to roles that are never used."""
        oidc_targets = set()
        for rel in trust_relationships:
            if rel.trust_type == "OIDC_Federation":
                oidc_targets.add(rel.target_identity_id)

        for identity in identities:
            if identity.id in oidc_targets and identity.last_used_at is None:
                result.debt_items.append(TrustDebtItem(
                    category="Unused OIDC Federation",
                    description=f"GitLab OIDC trusts '{identity.name}' but this role has never been used. "
                               f"The federation creates an unnecessary access path.",
                    points=DEBT_UNUSED_OIDC_FEDERATION,
                    affected_identity_id=str(identity.id),
                    affected_identity_name=identity.name,
                    recommendation="Remove the OIDC trust from this role's trust policy, or delete the role entirely.",
                ))

    async def _check_admin_on_oidc_roles(self, session, identities, result):
        """Debt: OIDC-trusted roles with admin access."""
        for identity in identities:
            metadata = identity.metadata_ or {}
            trust_policy = metadata.get("trust_policy", {})
            attached = metadata.get("attached_policies", [])

            is_oidc = any(
                "oidc" in str(stmt.get("Principal", {}).get("Federated", "")).lower()
                or "gitlab" in str(stmt.get("Principal", {}).get("Federated", "")).lower()
                for stmt in trust_policy.get("Statement", [])
            )

            has_admin = any(
                p.get("name") in ("AdministratorAccess", "PowerUserAccess")
                for p in attached
            )

            if is_oidc and has_admin:
                result.debt_items.append(TrustDebtItem(
                    category="Admin on CI/CD Role",
                    description=f"'{identity.name}' is trusted by CI/CD via OIDC AND has AdministratorAccess. "
                               f"This is the highest form of trust debt — any pipeline can become admin.",
                    points=DEBT_ADMIN_ON_OIDC_ROLE,
                    affected_identity_id=str(identity.id),
                    affected_identity_name=identity.name,
                    recommendation="Immediately replace AdministratorAccess with a deployment-specific "
                                  "policy scoped to only the services your pipeline needs.",
                ))

    async def _check_no_branch_restrictions(self, session, identities, result):
        """Debt: OIDC trust without branch restrictions."""
        for identity in identities:
            metadata = identity.metadata_ or {}
            trust_policy = metadata.get("trust_policy", {})

            for stmt in trust_policy.get("Statement", []):
                principal = stmt.get("Principal", {})
                if not isinstance(principal, dict):
                    continue
                federated = principal.get("Federated", "")

                if "oidc" in str(federated).lower() or "gitlab" in str(federated).lower():
                    conditions = stmt.get("Condition", {})
                    sub_value = ""
                    for cond_type in ("StringEquals", "StringLike"):
                        for key, value in conditions.get(cond_type, {}).items():
                            if "sub" in key:
                                sub_value = str(value)

                    if sub_value and "ref:" not in sub_value:
                        result.debt_items.append(TrustDebtItem(
                            category="No Branch Restriction",
                            description=f"'{identity.name}' can be assumed from any branch. "
                                       f"Feature branches and MRs can access this role.",
                            points=DEBT_NO_BRANCH_RESTRICTION,
                            affected_identity_id=str(identity.id),
                            affected_identity_name=identity.name,
                            recommendation="Add branch restriction to the OIDC sub condition: "
                                          "ref_type:branch:ref:main",
                        ))
                    break

    async def _check_unused_trust_relationships(self, session, identities, trust_relationships, result):
        """Debt: Trust relationships where the target role is unused."""
        identity_map = {i.id: i for i in identities}

        for rel in trust_relationships:
            target = identity_map.get(rel.target_identity_id)
            if target and target.last_used_at is None:
                # Skip if already counted in unused OIDC
                if rel.trust_type == "OIDC_Federation":
                    continue
                result.debt_items.append(TrustDebtItem(
                    category="Unused Trust Relationship",
                    description=f"Trust relationship ({rel.trust_type}) to '{target.name}' "
                               f"but this role has never been used.",
                    points=DEBT_UNUSED_TRUST_RELATIONSHIP,
                    affected_identity_id=str(target.id),
                    affected_identity_name=target.name,
                    recommendation="Remove this trust relationship or delete the unused target role.",
                ))

    async def _check_stale_identities_with_trust(self, session, identities, trust_relationships, result):
        """Debt: Identities that are stale (90+ days) but still have active trust."""
        now = datetime.now(timezone.utc)
        trusted_ids = set(rel.target_identity_id for rel in trust_relationships)

        for identity in identities:
            if identity.id not in trusted_ids:
                continue
            if identity.last_used_at is None:
                continue  # Already covered by unused checks
            days_unused = (now - identity.last_used_at).days
            if days_unused > 90:
                result.debt_items.append(TrustDebtItem(
                    category="Stale Trusted Identity",
                    description=f"'{identity.name}' hasn't been used in {days_unused} days "
                               f"but is still trusted by other identities.",
                    points=DEBT_STALE_IDENTITY_WITH_TRUST,
                    affected_identity_id=str(identity.id),
                    affected_identity_name=identity.name,
                    recommendation=f"Review if this role is still needed. Last used {days_unused} days ago.",
                    age_days=days_unused,
                ))

    async def _check_overprivileged_access(self, session, identities, result):
        """Debt: Roles with wildcard resource access."""
        for identity in identities:
            metadata = identity.metadata_ or {}
            all_policies = metadata.get("attached_policies", []) + metadata.get("inline_policies", [])

            for policy in all_policies:
                doc = policy.get("document", {})
                if isinstance(doc, str):
                    continue
                for stmt in doc.get("Statement", []):
                    if stmt.get("Effect") != "Allow":
                        continue
                    actions = stmt.get("Action", [])
                    resources = stmt.get("Resource", [])
                    if isinstance(actions, str):
                        actions = [actions]
                    if isinstance(resources, str):
                        resources = [resources]

                    if "*" in resources and "*" not in actions:
                        result.debt_items.append(TrustDebtItem(
                            category="Wildcard Resource Access",
                            description=f"'{identity.name}' has actions scoped but targets ALL resources (*). "
                                       f"Should be scoped to specific resource ARNs.",
                            points=DEBT_WILDCARD_RESOURCE_ACCESS,
                            affected_identity_id=str(identity.id),
                            affected_identity_name=identity.name,
                            recommendation="Scope the Resource field to specific ARNs instead of *.",
                        ))
                        break
                else:
                    continue
                break

    @staticmethod
    def _result_to_dict(result: TrustDebtResult) -> dict:
        return {
            "total_debt_score": result.total_debt_score,
            "max_possible_score": result.max_possible_score,
            "debt_percentage": result.debt_percentage,
            "debt_grade": result.debt_grade,
            "trend": result.trend,
            "category_breakdown": result.category_breakdown,
            "top_contributors": result.top_contributors,
            "debt_items": [
                {
                    "category": item.category,
                    "description": item.description,
                    "points": item.points,
                    "affected_identity_id": item.affected_identity_id,
                    "affected_identity_name": item.affected_identity_name,
                    "recommendation": item.recommendation,
                    "age_days": item.age_days,
                }
                for item in result.debt_items
            ],
            "total_items": len(result.debt_items),
        }
