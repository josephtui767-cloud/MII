"""Security Findings Engine — generates actionable security findings from identity data."""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.database import async_session_factory
from app.models import Identity, IdentityAccess, Resource, TrustRelationship

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Finding:
    id: str
    title: str
    severity: str
    category: str
    description: str
    affected_identity_id: str
    affected_identity_name: str
    remediation: str
    remediation_command: str = ""
    blast_radius: str = ""
    created_at: str = ""


class FindingsEngine:
    """Analyzes identity data and generates security findings."""

    def __init__(self):
        self.findings: list[Finding] = []

    async def generate_findings(self) -> list[dict]:
        """Generate all security findings from current identity data."""
        self.findings = []

        async with async_session_factory() as session:
            # Load all identities with relationships
            stmt = select(Identity)
            result = await session.execute(stmt)
            identities = result.scalars().all()

            for identity in identities:
                await self._check_admin_without_constraints(session, identity)
                await self._check_unused_identity(session, identity)
                await self._check_oidc_without_branch_restriction(session, identity)
                await self._check_overprivileged_oidc(session, identity)
                await self._check_cross_account_trust(session, identity)
                await self._check_wildcard_trust(session, identity)
                await self._check_production_access_without_mfa(session, identity)

        # Deduplicate: if OIDC-ADMIN exists for an identity, remove the plain ADMIN finding
        # (OIDC-ADMIN is more specific and higher priority)
        oidc_admin_ids = {f.affected_identity_id for f in self.findings if f.id.startswith("OIDC-ADMIN-")}
        self.findings = [
            f for f in self.findings
            if not (f.id.startswith("ADMIN-") and f.affected_identity_id in oidc_admin_ids)
        ]

        return [self._finding_to_dict(f) for f in self.findings]

    async def _check_admin_without_constraints(self, session, identity: Identity):
        """CRITICAL: Identity has admin access without conditions."""
        metadata = identity.metadata_ or {}
        attached_policies = metadata.get("attached_policies", [])

        has_admin = any(
            p.get("name") in ("AdministratorAccess", "PowerUserAccess")
            for p in attached_policies
        )

        if has_admin:
            # Check if there are OIDC conditions
            trust_policy = metadata.get("trust_policy", {})
            has_conditions = False
            for stmt in trust_policy.get("Statement", []):
                if stmt.get("Condition"):
                    has_conditions = True
                    break

            severity = Severity.CRITICAL if not has_conditions else Severity.HIGH

            self.findings.append(Finding(
                id=f"ADMIN-{identity.id}",
                title=f"Admin access on {identity.name}",
                severity=severity.value,
                category="Excessive Permissions",
                description=f"Role '{identity.name}' has AdministratorAccess policy attached, "
                           f"granting unrestricted access to all AWS services and resources. "
                           f"{'No conditions restrict who can assume this role.' if not has_conditions else 'Conditions exist but admin is still overprivileged.'}",
                affected_identity_id=str(identity.id),
                affected_identity_name=identity.name,
                remediation="Replace AdministratorAccess with a scoped policy that grants only the "
                           "specific permissions needed. Use AWS Access Analyzer to determine actual "
                           "permissions used in the last 90 days.",
                remediation_command=f"aws iam detach-role-policy --role-name {identity.name} "
                                   f"--policy-arn arn:aws:iam::aws:policy/AdministratorAccess",
                blast_radius="Full account compromise — all services and data accessible",
            ))

    async def _check_unused_identity(self, session, identity: Identity):
        """MEDIUM: Identity has not been used in 90+ days."""
        if identity.last_used_at is None:
            days_unused = "never"
            severity = Severity.MEDIUM
        else:
            days_unused = (datetime.now(timezone.utc) - identity.last_used_at).days
            if days_unused < 90:
                return
            severity = Severity.MEDIUM if days_unused < 180 else Severity.HIGH

        # Skip service-linked roles
        if "ServiceRole" in identity.name or "service-role" in identity.name.lower():
            return

        self.findings.append(Finding(
            id=f"UNUSED-{identity.id}",
            title=f"Unused identity: {identity.name}",
            severity=severity.value,
            category="Stale Identity",
            description=f"Role '{identity.name}' has not been used "
                       f"{'ever' if days_unused == 'never' else f'in {days_unused} days'}. "
                       f"Unused identities increase attack surface without providing value.",
            affected_identity_id=str(identity.id),
            affected_identity_name=identity.name,
            remediation="Review if this role is still needed. If not, delete it. "
                       "If uncertain, remove all policies first and monitor for 14 days.",
            remediation_command=f"aws iam delete-role --role-name {identity.name}",
            blast_radius="Low direct impact but increases overall attack surface",
        ))

    async def _check_oidc_without_branch_restriction(self, session, identity: Identity):
        """HIGH: OIDC trust allows any branch to assume the role."""
        metadata = identity.metadata_ or {}
        trust_policy = metadata.get("trust_policy", {})

        for stmt in trust_policy.get("Statement", []):
            principal = stmt.get("Principal", {})
            federated = principal.get("Federated", "")

            if "oidc" in str(federated).lower() or "gitlab" in str(federated).lower():
                conditions = stmt.get("Condition", {})
                sub_condition = ""

                for cond_type in ("StringEquals", "StringLike"):
                    for key, value in conditions.get(cond_type, {}).items():
                        if "sub" in key:
                            sub_condition = str(value)

                # Check if restricted to specific branch
                if sub_condition and "ref:" not in sub_condition and "ref_type:" not in sub_condition:
                    self.findings.append(Finding(
                        id=f"OIDC-BRANCH-{identity.id}",
                        title=f"OIDC trust without branch restriction: {identity.name}",
                        severity=Severity.HIGH.value,
                        category="Trust Configuration",
                        description=f"Role '{identity.name}' can be assumed by GitLab CI/CD from ANY branch. "
                                   f"This means feature branches, forks, and merge requests can all assume "
                                   f"this role. Condition: {sub_condition}",
                        affected_identity_id=str(identity.id),
                        affected_identity_name=identity.name,
                        remediation="Restrict the OIDC trust to specific branches (e.g., main only) by adding "
                                   "'ref_type:branch:ref:main' to the sub condition in the trust policy.",
                        remediation_command="",
                        blast_radius="Any CI/CD pipeline in the project can assume this role",
                    ))
                break

    async def _check_overprivileged_oidc(self, session, identity: Identity):
        """CRITICAL: OIDC-trusted role has admin permissions."""
        metadata = identity.metadata_ or {}
        trust_policy = metadata.get("trust_policy", {})
        attached_policies = metadata.get("attached_policies", [])

        is_oidc_trusted = False
        for stmt in trust_policy.get("Statement", []):
            principal = stmt.get("Principal", {})
            federated = principal.get("Federated", "")
            if "oidc" in str(federated).lower() or "gitlab" in str(federated).lower():
                is_oidc_trusted = True
                break

        if not is_oidc_trusted:
            return

        has_admin = any(
            p.get("name") in ("AdministratorAccess", "PowerUserAccess")
            for p in attached_policies
        )

        if has_admin:
            self.findings.append(Finding(
                id=f"OIDC-ADMIN-{identity.id}",
                title=f"CRITICAL: CI/CD pipeline has admin access via {identity.name}",
                severity=Severity.CRITICAL.value,
                category="Excessive Permissions + Trust Chain",
                description=f"Role '{identity.name}' is assumable by GitLab CI/CD via OIDC AND has "
                           f"AdministratorAccess. This means any CI/CD pipeline can get full admin "
                           f"access to the AWS account. This is the highest risk finding.",
                affected_identity_id=str(identity.id),
                affected_identity_name=identity.name,
                remediation="1. Immediately scope down permissions to only what the pipeline needs. "
                           "2. Add branch restrictions to the OIDC trust policy. "
                           "3. Enable CloudTrail logging to detect misuse.",
                remediation_command=f"aws iam detach-role-policy --role-name {identity.name} "
                                   f"--policy-arn arn:aws:iam::aws:policy/AdministratorAccess",
                blast_radius="FULL ACCOUNT COMPROMISE — any pipeline contributor can become admin",
            ))

    async def _check_cross_account_trust(self, session, identity: Identity):
        """HIGH: Role is trusted by external AWS account."""
        stmt = select(TrustRelationship).where(
            TrustRelationship.target_identity_id == identity.id,
            TrustRelationship.trust_type == "Cross_Account_Trust",
        )
        result = await session.execute(stmt)
        cross_trusts = result.scalars().all()

        if cross_trusts:
            accounts = [t.external_account_id or "unknown" for t in cross_trusts]
            self.findings.append(Finding(
                id=f"CROSS-ACCOUNT-{identity.id}",
                title=f"Cross-account trust: {identity.name}",
                severity=Severity.HIGH.value,
                category="Trust Configuration",
                description=f"Role '{identity.name}' trusts external AWS account(s): {', '.join(accounts)}. "
                           f"Principals in those accounts can assume this role.",
                affected_identity_id=str(identity.id),
                affected_identity_name=identity.name,
                remediation="Verify the external accounts are known and authorized. Add condition "
                           "keys (ExternalId, MFA) to restrict assumption.",
                remediation_command="",
                blast_radius=f"External account(s) {', '.join(accounts)} can access resources via this role",
            ))

    async def _check_wildcard_trust(self, session, identity: Identity):
        """CRITICAL: Role trust policy allows wildcard principal."""
        metadata = identity.metadata_ or {}
        trust_policy = metadata.get("trust_policy", {})

        for stmt in trust_policy.get("Statement", []):
            principal = stmt.get("Principal", "")
            if principal == "*" or (isinstance(principal, dict) and principal.get("AWS") == "*"):
                self.findings.append(Finding(
                    id=f"WILDCARD-TRUST-{identity.id}",
                    title=f"Wildcard trust policy: {identity.name}",
                    severity=Severity.CRITICAL.value,
                    category="Trust Configuration",
                    description=f"Role '{identity.name}' has a wildcard (*) principal in its trust policy. "
                               f"This means ANY AWS account or identity can assume this role.",
                    affected_identity_id=str(identity.id),
                    affected_identity_name=identity.name,
                    remediation="Remove the wildcard principal and replace with specific account IDs "
                               "or role ARNs that should have access.",
                    remediation_command="",
                    blast_radius="ANY AWS identity worldwide can assume this role",
                ))
                break

    async def _check_production_access_without_mfa(self, session, identity: Identity):
        """MEDIUM: Identity accesses production without MFA condition."""
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
            metadata = identity.metadata_ or {}
            trust_policy = metadata.get("trust_policy", {})

            has_mfa = False
            for stmt_item in trust_policy.get("Statement", []):
                conditions = stmt_item.get("Condition", {})
                for cond_type, cond_values in conditions.items():
                    for key in cond_values:
                        if "mfa" in key.lower() or "MultiFactorAuth" in key:
                            has_mfa = True
                            break

            if not has_mfa and not identity.name.startswith("AWSServiceRole"):
                self.findings.append(Finding(
                    id=f"PROD-NO-MFA-{identity.id}",
                    title=f"Production access without MFA: {identity.name}",
                    severity=Severity.MEDIUM.value,
                    category="Access Control",
                    description=f"Role '{identity.name}' can access {prod_count} production resource(s) "
                               f"but does not require MFA for assumption.",
                    affected_identity_id=str(identity.id),
                    affected_identity_name=identity.name,
                    remediation="Add an MFA condition to the trust policy to require multi-factor "
                               "authentication before the role can be assumed.",
                    remediation_command="",
                    blast_radius=f"{prod_count} production resource(s) accessible without MFA",
                ))

    @staticmethod
    def _finding_to_dict(finding: Finding) -> dict:
        return {
            "id": finding.id,
            "title": finding.title,
            "severity": finding.severity,
            "category": finding.category,
            "description": finding.description,
            "affected_identity_id": finding.affected_identity_id,
            "affected_identity_name": finding.affected_identity_name,
            "remediation": finding.remediation,
            "remediation_command": finding.remediation_command,
            "blast_radius": finding.blast_radius,
        }
