"""Risk Engine — calculates risk scores for machine identities based on weighted factors."""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.database import async_session_factory
from app.models import Identity, IdentityAccess, Resource, TrustRelationship

logger = logging.getLogger(__name__)

# Risk factor weights (per design document)
WEIGHT_ADMIN_PERMISSIONS = 35
WEIGHT_PRODUCTION_ACCESS = 25
WEIGHT_TRUST_RELATIONSHIP_COUNT = 20
WEIGHT_CROSS_ACCOUNT_ACCESS = 20
WEIGHT_STALENESS = 15
WEIGHT_UNUSED = 10

# Thresholds
TRUST_COUNT_THRESHOLD = 10
STALENESS_DAYS_THRESHOLD = 90

# Admin policy indicators
ADMIN_POLICY_NAMES = {"AdministratorAccess", "PowerUserAccess", "IAMFullAccess"}


@dataclass
class RiskFactor:
    factor: str
    points: int
    reason: str


@dataclass
class RiskResult:
    identity_id: uuid.UUID
    identity_name: str
    score: int
    factors: list[RiskFactor] = field(default_factory=list)
    unevaluable_factors: list[str] = field(default_factory=list)


class RiskEngine:
    """Calculates risk scores for all identities based on six weighted factors."""

    def __init__(self):
        self.processed = 0
        self.errors: list[str] = []

    async def recalculate_all(self) -> dict:
        """Recalculate risk scores for every identity in the database.

        Returns summary with count of processed identities.
        """
        self.processed = 0
        self.errors = []

        async with async_session_factory() as session:
            stmt = select(Identity)
            result = await session.execute(stmt)
            identities = result.scalars().all()

            logger.info(f"Recalculating risk scores for {len(identities)} identities")

            for identity in identities:
                try:
                    risk_result = await self._calculate_score(session, identity)
                    identity.risk_score = risk_result.score
                    identity.risk_factors = [
                        {"factor": f.factor, "points": f.points, "reason": f.reason}
                        for f in risk_result.factors
                    ]
                    self.processed += 1
                except Exception as e:
                    error_msg = f"Error calculating risk for {identity.name}: {e}"
                    logger.warning(error_msg)
                    self.errors.append(error_msg)

            await session.commit()

        logger.info(f"Risk recalculation complete: {self.processed} identities processed")
        return {
            "identities_processed": self.processed,
            "errors": self.errors,
        }

    async def calculate_for_identity(self, identity_id: uuid.UUID) -> RiskResult | None:
        """Calculate risk score for a single identity."""
        async with async_session_factory() as session:
            stmt = select(Identity).where(Identity.id == identity_id)
            result = await session.execute(stmt)
            identity = result.scalar_one_or_none()

            if not identity:
                return None

            risk_result = await self._calculate_score(session, identity)

            # Persist
            identity.risk_score = risk_result.score
            identity.risk_factors = [
                {"factor": f.factor, "points": f.points, "reason": f.reason}
                for f in risk_result.factors
            ]
            await session.commit()

            return risk_result

    async def _calculate_score(self, session, identity: Identity) -> RiskResult:
        """Apply all six risk factors and return the result."""
        factors: list[RiskFactor] = []
        unevaluable: list[str] = []
        total = 0

        # Factor 1: Admin permissions
        admin_result = await self._check_admin_permissions(session, identity)
        if admin_result is not None:
            if admin_result:
                factors.append(admin_result)
                total += admin_result.points
        else:
            unevaluable.append("admin_permissions")

        # Factor 2: Production access
        prod_result = await self._check_production_access(session, identity)
        if prod_result is not None:
            if prod_result:
                factors.append(prod_result)
                total += prod_result.points
        else:
            unevaluable.append("production_access")

        # Factor 3: Trust relationship count
        trust_result = await self._check_trust_count(session, identity)
        if trust_result:
            factors.append(trust_result)
            total += trust_result.points

        # Factor 4: Cross-account access
        cross_result = await self._check_cross_account(session, identity)
        if cross_result:
            factors.append(cross_result)
            total += cross_result.points

        # Factor 5: Staleness / Factor 6: Unused
        staleness_result = self._check_staleness(identity)
        if staleness_result is not None:
            if staleness_result:
                factors.append(staleness_result)
                total += staleness_result.points
        else:
            unevaluable.append("staleness")

        # Cap at 100
        score = min(total, 100)

        return RiskResult(
            identity_id=identity.id,
            identity_name=identity.name,
            score=score,
            factors=factors,
            unevaluable_factors=unevaluable,
        )

    async def _check_admin_permissions(self, session, identity: Identity) -> RiskFactor | None | bool:
        """Check if identity has admin/wildcard permissions.

        Returns RiskFactor if admin, False if not admin, None if can't evaluate.
        """
        metadata = identity.metadata_ or {}

        # Check attached policy names for known admin policies
        attached_policies = metadata.get("attached_policies", [])
        for policy in attached_policies:
            policy_name = policy.get("name", "")
            if policy_name in ADMIN_POLICY_NAMES:
                return RiskFactor(
                    factor="admin_permissions",
                    points=WEIGHT_ADMIN_PERMISSIONS,
                    reason=f"Has {policy_name} policy",
                )

        # Check for wildcard actions in any policy document
        all_policies = attached_policies + metadata.get("inline_policies", [])
        if not all_policies:
            # No policies to evaluate — check access records
            stmt = select(IdentityAccess).where(
                IdentityAccess.identity_id == identity.id,
                IdentityAccess.access_type == "Admin",
            )
            result = await session.execute(stmt)
            admin_access = result.scalars().first()
            if admin_access:
                return RiskFactor(
                    factor="admin_permissions",
                    points=WEIGHT_ADMIN_PERMISSIONS,
                    reason="Has Admin-level resource access",
                )
            return False

        for policy in all_policies:
            document = policy.get("document", {})
            if isinstance(document, str):
                import json
                try:
                    document = json.loads(document)
                except Exception:
                    continue

            for statement in document.get("Statement", []):
                if statement.get("Effect") != "Allow":
                    continue
                actions = statement.get("Action", [])
                resources = statement.get("Resource", [])
                if isinstance(actions, str):
                    actions = [actions]
                if isinstance(resources, str):
                    resources = [resources]

                # Check for full wildcard: Action=* AND Resource=*
                if "*" in actions and "*" in resources:
                    return RiskFactor(
                        factor="admin_permissions",
                        points=WEIGHT_ADMIN_PERMISSIONS,
                        reason="Has wildcard (*) action on all resources (*)",
                    )

                # Check for service-level wildcards (e.g., iam:*)
                for action in actions:
                    if action.endswith(":*") and "*" in resources:
                        return RiskFactor(
                            factor="admin_permissions",
                            points=WEIGHT_ADMIN_PERMISSIONS,
                            reason=f"Has service wildcard ({action}) on all resources",
                        )

        return False

    async def _check_production_access(self, session, identity: Identity) -> RiskFactor | None | bool:
        """Check if identity can access production resources.

        Returns RiskFactor if production access, False if not, None if can't evaluate.
        """
        stmt = (
            select(func.count())
            .select_from(IdentityAccess)
            .join(Resource, IdentityAccess.resource_id == Resource.id)
            .where(
                IdentityAccess.identity_id == identity.id,
                Resource.classification == "production",
            )
        )
        result = await session.execute(stmt)
        prod_count = result.scalar() or 0

        if prod_count > 0:
            return RiskFactor(
                factor="production_access",
                points=WEIGHT_PRODUCTION_ACCESS,
                reason=f"Accesses {prod_count} production resource{'s' if prod_count > 1 else ''}",
            )

        return False

    async def _check_trust_count(self, session, identity: Identity) -> RiskFactor | None:
        """Check how many identities trust this one (incoming trust count)."""
        stmt = (
            select(func.count())
            .select_from(TrustRelationship)
            .where(TrustRelationship.target_identity_id == identity.id)
        )
        result = await session.execute(stmt)
        trust_count = result.scalar() or 0

        if trust_count > TRUST_COUNT_THRESHOLD:
            return RiskFactor(
                factor="trust_relationship_count",
                points=WEIGHT_TRUST_RELATIONSHIP_COUNT,
                reason=f"Trusted by {trust_count} identities (threshold: {TRUST_COUNT_THRESHOLD})",
            )

        return None

    async def _check_cross_account(self, session, identity: Identity) -> RiskFactor | None:
        """Check if identity has cross-account trust relationships."""
        stmt = (
            select(func.count())
            .select_from(TrustRelationship)
            .where(
                TrustRelationship.target_identity_id == identity.id,
                TrustRelationship.trust_type == "Cross_Account_Trust",
            )
        )
        result = await session.execute(stmt)
        cross_count = result.scalar() or 0

        if cross_count > 0:
            return RiskFactor(
                factor="cross_account_access",
                points=WEIGHT_CROSS_ACCOUNT_ACCESS,
                reason=f"Trusted by {cross_count} external account{'s' if cross_count > 1 else ''}",
            )

        return None

    def _check_staleness(self, identity: Identity) -> RiskFactor | None | bool:
        """Check if identity is stale (unused 90+ days) or never used.

        Returns RiskFactor if stale/unused, False if recently used, None if can't evaluate.
        """
        if identity.last_used_at is None:
            # Never used
            return RiskFactor(
                factor="unused",
                points=WEIGHT_UNUSED,
                reason="Has never been used",
            )

        now = datetime.now(timezone.utc)
        days_unused = (now - identity.last_used_at).days

        if days_unused > STALENESS_DAYS_THRESHOLD:
            return RiskFactor(
                factor="staleness",
                points=WEIGHT_STALENESS,
                reason=f"Not used in {days_unused} days (threshold: {STALENESS_DAYS_THRESHOLD})",
            )

        return False
