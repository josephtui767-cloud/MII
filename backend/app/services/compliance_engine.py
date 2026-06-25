"""Compliance Engine — checks identities against security policies and generates pass/fail results."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.database import async_session_factory
from app.models import Identity, IdentityAccess, Resource, TrustRelationship

logger = logging.getLogger(__name__)


@dataclass
class ComplianceCheck:
    id: str
    policy_name: str
    description: str
    severity: str  # critical, high, medium, low
    status: str = "pending"  # pass, fail, warning
    total_checked: int = 0
    passing: int = 0
    failing: int = 0
    failing_identities: list = field(default_factory=list)
    recommendation: str = ""


class ComplianceEngine:
    """Checks identity landscape against security policies."""

    async def run_all_checks(self) -> dict:
        """Run all compliance checks and return summary."""
        checks: list[ComplianceCheck] = []

        async with async_session_factory() as session:
            stmt = select(Identity)
            result = await session.execute(stmt)
            identities = result.scalars().all()

            checks.append(await self._check_no_admin_access(session, identities))
            checks.append(await self._check_least_privilege(session, identities))
            checks.append(await self._check_no_unused_identities(session, identities))
            checks.append(await self._check_oidc_branch_restriction(session, identities))
            checks.append(await self._check_no_wildcard_trust(session, identities))
            checks.append(await self._check_mfa_for_production(session, identities))
            checks.append(await self._check_identity_lifecycle(session, identities))
            checks.append(await self._check_no_cross_account_without_external_id(session, identities))

        total_checks = len(checks)
        passing_checks = sum(1 for c in checks if c.status == "pass")
        failing_checks = sum(1 for c in checks if c.status == "fail")
        warning_checks = sum(1 for c in checks if c.status == "warning")

        compliance_score = round((passing_checks / total_checks) * 100) if total_checks > 0 else 0

        return {
            "compliance_score": compliance_score,
            "total_checks": total_checks,
            "passing": passing_checks,
            "failing": failing_checks,
            "warnings": warning_checks,
            "checks": [self._check_to_dict(c) for c in checks],
        }

    async def _check_no_admin_access(self, session, identities: list[Identity]) -> ComplianceCheck:
        """Policy: No identity should have unrestricted admin access."""
        check = ComplianceCheck(
            id="CMP-001",
            policy_name="No Unrestricted Admin Access",
            description="No machine identity should have AdministratorAccess or wildcard (*) permissions",
            severity="critical",
            recommendation="Replace admin policies with scoped policies using least-privilege principle",
            total_checked=len(identities),
        )

        for identity in identities:
            metadata = identity.metadata_ or {}
            attached = metadata.get("attached_policies", [])
            has_admin = any(p.get("name") in ("AdministratorAccess", "PowerUserAccess") for p in attached)

            if has_admin:
                check.failing += 1
                check.failing_identities.append({
                    "id": str(identity.id),
                    "name": identity.name,
                    "reason": "Has AdministratorAccess policy",
                })
            else:
                check.passing += 1

        check.status = "pass" if check.failing == 0 else "fail"
        return check

    async def _check_least_privilege(self, session, identities: list[Identity]) -> ComplianceCheck:
        """Policy: All identities should follow least privilege (no wildcard resources)."""
        check = ComplianceCheck(
            id="CMP-002",
            policy_name="Least Privilege Principle",
            description="No identity should have wildcard (*) resource access in Allow statements",
            severity="high",
            recommendation="Scope resource ARNs to specific resources instead of wildcards",
            total_checked=len(identities),
        )

        for identity in identities:
            metadata = identity.metadata_ or {}
            all_policies = metadata.get("attached_policies", []) + metadata.get("inline_policies", [])

            has_wildcard = False
            for policy in all_policies:
                doc = policy.get("document", {})
                if isinstance(doc, str):
                    continue
                for stmt in doc.get("Statement", []):
                    if stmt.get("Effect") != "Allow":
                        continue
                    resources = stmt.get("Resource", [])
                    if isinstance(resources, str):
                        resources = [resources]
                    if "*" in resources:
                        has_wildcard = True
                        break
                if has_wildcard:
                    break

            if has_wildcard:
                check.failing += 1
                check.failing_identities.append({
                    "id": str(identity.id),
                    "name": identity.name,
                    "reason": "Has wildcard (*) resource in Allow statement",
                })
            else:
                check.passing += 1

        check.status = "pass" if check.failing == 0 else "fail"
        return check

    async def _check_no_unused_identities(self, session, identities: list[Identity]) -> ComplianceCheck:
        """Policy: No identity should be unused for more than 90 days."""
        check = ComplianceCheck(
            id="CMP-003",
            policy_name="No Stale Identities",
            description="All machine identities must be used within the last 90 days or be removed",
            severity="medium",
            recommendation="Delete unused identities or document exception with expiry date",
            total_checked=len(identities),
        )

        now = datetime.now(timezone.utc)
        for identity in identities:
            if identity.name.startswith("AWSServiceRole"):
                check.passing += 1
                continue

            if identity.last_used_at is None:
                check.failing += 1
                check.failing_identities.append({
                    "id": str(identity.id),
                    "name": identity.name,
                    "reason": "Never used",
                })
            elif (now - identity.last_used_at).days > 90:
                check.failing += 1
                check.failing_identities.append({
                    "id": str(identity.id),
                    "name": identity.name,
                    "reason": f"Unused for {(now - identity.last_used_at).days} days",
                })
            else:
                check.passing += 1

        check.status = "pass" if check.failing == 0 else ("warning" if check.failing <= 2 else "fail")
        return check

    async def _check_oidc_branch_restriction(self, session, identities: list[Identity]) -> ComplianceCheck:
        """Policy: OIDC-trusted roles must restrict to specific branches."""
        check = ComplianceCheck(
            id="CMP-004",
            policy_name="OIDC Branch Restriction",
            description="All OIDC-trusted roles must restrict assumption to specific branches (e.g., main)",
            severity="high",
            recommendation="Add ref_type:branch:ref:main to OIDC sub condition in trust policy",
            total_checked=0,
        )

        for identity in identities:
            metadata = identity.metadata_ or {}
            trust_policy = metadata.get("trust_policy", {})

            for stmt in trust_policy.get("Statement", []):
                principal = stmt.get("Principal", {})
                federated = principal.get("Federated", "")

                if "oidc" in str(federated).lower() or "gitlab" in str(federated).lower():
                    check.total_checked += 1
                    conditions = stmt.get("Condition", {})
                    sub_value = ""
                    for cond_type in ("StringEquals", "StringLike"):
                        for key, value in conditions.get(cond_type, {}).items():
                            if "sub" in key:
                                sub_value = str(value)

                    if "ref:" in sub_value or "ref_type:" in sub_value:
                        check.passing += 1
                    else:
                        check.failing += 1
                        check.failing_identities.append({
                            "id": str(identity.id),
                            "name": identity.name,
                            "reason": "OIDC trust allows any branch",
                        })
                    break

        if check.total_checked == 0:
            check.status = "pass"
            check.total_checked = len(identities)
            check.passing = len(identities)
        else:
            check.status = "pass" if check.failing == 0 else "fail"

        return check

    async def _check_no_wildcard_trust(self, session, identities: list[Identity]) -> ComplianceCheck:
        """Policy: No role should have wildcard (*) trust principal."""
        check = ComplianceCheck(
            id="CMP-005",
            policy_name="No Wildcard Trust",
            description="No role should allow any AWS identity to assume it (wildcard principal)",
            severity="critical",
            recommendation="Replace wildcard principal with specific account IDs or role ARNs",
            total_checked=len(identities),
        )

        for identity in identities:
            metadata = identity.metadata_ or {}
            trust_policy = metadata.get("trust_policy", {})

            has_wildcard = False
            for stmt in trust_policy.get("Statement", []):
                principal = stmt.get("Principal", "")
                if principal == "*":
                    has_wildcard = True
                elif isinstance(principal, dict) and principal.get("AWS") == "*":
                    has_wildcard = True

            if has_wildcard:
                check.failing += 1
                check.failing_identities.append({
                    "id": str(identity.id),
                    "name": identity.name,
                    "reason": "Wildcard (*) principal in trust policy",
                })
            else:
                check.passing += 1

        check.status = "pass" if check.failing == 0 else "fail"
        return check

    async def _check_mfa_for_production(self, session, identities: list[Identity]) -> ComplianceCheck:
        """Policy: Production access should require MFA."""
        check = ComplianceCheck(
            id="CMP-006",
            policy_name="MFA for Production Access",
            description="Roles accessing production resources should require MFA for assumption",
            severity="medium",
            recommendation="Add aws:MultiFactorAuthPresent condition to trust policy",
            total_checked=0,
        )

        for identity in identities:
            if identity.name.startswith("AWSServiceRole"):
                continue

            try:
                query = (
                    select(func.count())
                    .select_from(IdentityAccess)
                    .join(Resource, IdentityAccess.resource_id == Resource.id)
                    .where(
                        IdentityAccess.identity_id == identity.id,
                        Resource.classification == "production",
                    )
                )
                result = await session.execute(query)
                prod_count = result.scalar() or 0
            except Exception:
                continue

            if prod_count > 0:
                check.total_checked += 1
                metadata = identity.metadata_ or {}
                trust_policy = metadata.get("trust_policy", {})

                has_mfa = False
                for policy_stmt in trust_policy.get("Statement", []):
                    conditions = policy_stmt.get("Condition", {})
                    for cond_values in conditions.values():
                        if isinstance(cond_values, dict):
                            for key in cond_values:
                                if "mfa" in key.lower() or "MultiFactorAuth" in key:
                                    has_mfa = True

                if has_mfa:
                    check.passing += 1
                else:
                    check.failing += 1
                    check.failing_identities.append({
                        "id": str(identity.id),
                        "name": identity.name,
                        "reason": f"Accesses {prod_count} production resources without MFA",
                    })

        if check.total_checked == 0:
            check.status = "pass"
            check.total_checked = len(identities)
            check.passing = len(identities)
        else:
            check.status = "pass" if check.failing == 0 else "fail"

        return check

    async def _check_identity_lifecycle(self, session, identities: list[Identity]) -> ComplianceCheck:
        """Policy: All identities should have an owner assigned."""
        check = ComplianceCheck(
            id="CMP-007",
            policy_name="Identity Ownership",
            description="All machine identities must have a documented owner for accountability",
            severity="low",
            recommendation="Assign owners via resource tags or a CMDB entry",
            total_checked=len(identities),
        )

        for identity in identities:
            if identity.owner:
                check.passing += 1
            else:
                check.failing += 1
                check.failing_identities.append({
                    "id": str(identity.id),
                    "name": identity.name,
                    "reason": "No owner assigned",
                })

        check.status = "pass" if check.failing == 0 else ("warning" if check.failing < len(identities) / 2 else "fail")
        return check

    async def _check_no_cross_account_without_external_id(self, session, identities: list[Identity]) -> ComplianceCheck:
        """Policy: Cross-account trust should use ExternalId condition."""
        check = ComplianceCheck(
            id="CMP-008",
            policy_name="Cross-Account ExternalId",
            description="Cross-account trust relationships should use ExternalId to prevent confused deputy",
            severity="high",
            recommendation="Add sts:ExternalId condition to cross-account trust policies",
            total_checked=0,
        )

        for identity in identities:
            metadata = identity.metadata_ or {}
            trust_policy = metadata.get("trust_policy", {})

            for policy_stmt in trust_policy.get("Statement", []):
                principal = policy_stmt.get("Principal", {})
                if not isinstance(principal, dict):
                    continue
                aws_principals = principal.get("AWS", [])
                if isinstance(aws_principals, str):
                    aws_principals = [aws_principals]

                for arn in aws_principals:
                    if arn == "*":
                        continue
                    # Check if it's a different account
                    parts = arn.split(":")
                    if len(parts) >= 5 and parts[4] != str(identity.account_id) and parts[4].isdigit():
                        check.total_checked += 1
                        conditions = policy_stmt.get("Condition", {})
                        has_external_id = False
                        for cond_values in conditions.values():
                            if isinstance(cond_values, dict):
                                if "sts:ExternalId" in cond_values or "aws:ExternalId" in cond_values:
                                    has_external_id = True

                        if has_external_id:
                            check.passing += 1
                        else:
                            check.failing += 1
                            check.failing_identities.append({
                                "id": str(identity.id),
                                "name": identity.name,
                                "reason": f"Cross-account trust to {parts[4]} without ExternalId",
                            })

        if check.total_checked == 0:
            check.status = "pass"
            check.total_checked = len(identities)
            check.passing = len(identities)
        else:
            check.status = "pass" if check.failing == 0 else "fail"

        return check

    @staticmethod
    def _check_to_dict(check: ComplianceCheck) -> dict:
        return {
            "id": check.id,
            "policy_name": check.policy_name,
            "description": check.description,
            "status": check.status,
            "severity": check.severity,
            "total_checked": check.total_checked,
            "passing": check.passing,
            "failing": check.failing,
            "failing_identities": check.failing_identities[:10],  # Limit to 10
            "recommendation": check.recommendation,
        }
