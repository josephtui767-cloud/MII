"""Recommendations Engine — generates prioritized actionable recommendations."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.database import async_session_factory
from app.models import Identity, IdentityAccess, Resource, TrustRelationship

logger = logging.getLogger(__name__)


@dataclass
class Recommendation:
    id: str
    priority: str  # critical, high, medium, low
    title: str
    description: str
    action: str
    effort: str  # quick-win, moderate, significant
    impact: str  # high, medium, low
    affected_identities: list = field(default_factory=list)
    terraform_snippet: str = ""
    cli_command: str = ""


class RecommendationsEngine:
    """Generates prioritized remediation recommendations."""

    async def generate_recommendations(self) -> list[dict]:
        """Generate all recommendations based on current identity landscape."""
        recommendations: list[Recommendation] = []

        async with async_session_factory() as session:
            stmt = select(Identity)
            result = await session.execute(stmt)
            identities = result.scalars().all()

            # Analyze and generate recommendations
            recommendations.extend(await self._recommend_remove_admin(session, identities))
            recommendations.extend(await self._recommend_delete_unused(session, identities))
            recommendations.extend(await self._recommend_restrict_oidc_branches(session, identities))
            recommendations.extend(await self._recommend_scope_permissions(session, identities))
            recommendations.extend(await self._recommend_add_monitoring(session, identities))

        # Sort by priority
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        recommendations.sort(key=lambda r: priority_order.get(r.priority, 99))

        return [self._rec_to_dict(r) for r in recommendations]

    async def _recommend_remove_admin(self, session, identities: list[Identity]) -> list[Recommendation]:
        """Recommend removing admin access from OIDC-trusted roles."""
        recs = []
        admin_oidc_roles = []

        for identity in identities:
            metadata = identity.metadata_ or {}
            attached = metadata.get("attached_policies", [])
            trust_policy = metadata.get("trust_policy", {})

            has_admin = any(p.get("name") in ("AdministratorAccess", "PowerUserAccess") for p in attached)
            is_oidc = any(
                "oidc" in str(stmt.get("Principal", {}).get("Federated", "")).lower()
                or "gitlab" in str(stmt.get("Principal", {}).get("Federated", "")).lower()
                for stmt in trust_policy.get("Statement", [])
            )

            if has_admin and is_oidc:
                admin_oidc_roles.append(identity)

        if admin_oidc_roles:
            recs.append(Recommendation(
                id="REC-001",
                priority="critical",
                title="Remove admin access from CI/CD-trusted roles",
                description="CI/CD pipelines should never have full admin access. "
                           "Use least-privilege policies scoped to specific services needed for deployment.",
                action="Replace AdministratorAccess with a deployment-specific policy that only "
                      "allows the actions your pipeline actually performs (e.g., ECS deploy, S3 sync, CloudFront invalidation).",
                effort="moderate",
                impact="high",
                affected_identities=[{"id": str(i.id), "name": i.name} for i in admin_oidc_roles],
                cli_command="aws iam detach-role-policy --role-name ROLE_NAME --policy-arn arn:aws:iam::aws:policy/AdministratorAccess",
                terraform_snippet="""resource "aws_iam_role_policy" "deploy_only" {
  name = "deploy-only-policy"
  role = aws_iam_role.deploy.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:PutObject", "s3:GetObject", "s3:ListBucket", "s3:DeleteObject",
        "cloudfront:CreateInvalidation",
        "ecs:UpdateService", "ecs:DescribeServices"
      ]
      Resource = "*"
    }]
  })
}""",
            ))

        return recs

    async def _recommend_delete_unused(self, session, identities: list[Identity]) -> list[Recommendation]:
        """Recommend deleting unused identities."""
        recs = []
        unused_roles = []

        now = datetime.now(timezone.utc)
        for identity in identities:
            if identity.name.startswith("AWSServiceRole"):
                continue
            if identity.last_used_at is None or (now - identity.last_used_at).days > 90:
                unused_roles.append(identity)

        if unused_roles:
            recs.append(Recommendation(
                id="REC-002",
                priority="medium",
                title=f"Remove {len(unused_roles)} unused identities",
                description="These identities haven't been used in 90+ days. "
                           "Each unused identity is an unnecessary attack vector.",
                action="Review each identity. If no longer needed, delete it. "
                      "If uncertain, remove all policies and monitor for 14 days before deleting.",
                effort="quick-win",
                impact="medium",
                affected_identities=[{"id": str(i.id), "name": i.name} for i in unused_roles[:10]],
                cli_command="aws iam delete-role --role-name ROLE_NAME",
            ))

        return recs

    async def _recommend_restrict_oidc_branches(self, session, identities: list[Identity]) -> list[Recommendation]:
        """Recommend adding branch restrictions to OIDC trust."""
        recs = []
        unrestricted_oidc = []

        for identity in identities:
            metadata = identity.metadata_ or {}
            trust_policy = metadata.get("trust_policy", {})

            for stmt in trust_policy.get("Statement", []):
                principal = stmt.get("Principal", {})
                federated = principal.get("Federated", "")

                if "oidc" in str(federated).lower() or "gitlab" in str(federated).lower():
                    conditions = stmt.get("Condition", {})
                    sub_value = ""
                    for cond_type in ("StringEquals", "StringLike"):
                        for key, value in conditions.get(cond_type, {}).items():
                            if "sub" in key:
                                sub_value = str(value)

                    if sub_value and "ref:" not in sub_value:
                        unrestricted_oidc.append(identity)
                    break

        if unrestricted_oidc:
            recs.append(Recommendation(
                id="REC-003",
                priority="high",
                title="Add branch restrictions to OIDC trust policies",
                description="OIDC-trusted roles can currently be assumed from any branch. "
                           "This means feature branches and merge requests can access production AWS resources.",
                action="Update the trust policy sub condition to include branch restrictions. "
                      "Only allow main/production branches to assume sensitive roles.",
                effort="quick-win",
                impact="high",
                affected_identities=[{"id": str(i.id), "name": i.name} for i in unrestricted_oidc],
                terraform_snippet="""Condition = {
  StringLike = {
    "gitlab.com:sub" = "project_path:GROUP/PROJECT:ref_type:branch:ref:main"
  }
}""",
            ))

        return recs

    async def _recommend_scope_permissions(self, session, identities: list[Identity]) -> list[Recommendation]:
        """Recommend scoping down broad permissions."""
        recs = []
        broad_roles = []

        for identity in identities:
            metadata = identity.metadata_ or {}
            attached = metadata.get("attached_policies", [])

            # Check for broad AWS managed policies
            broad_policies = ["ReadOnlyAccess", "AmazonS3FullAccess", "AmazonEC2FullAccess"]
            has_broad = any(p.get("name") in broad_policies for p in attached)

            if has_broad:
                broad_roles.append(identity)

        if broad_roles:
            recs.append(Recommendation(
                id="REC-004",
                priority="medium",
                title="Scope down broad managed policies",
                description="Some roles use broad AWS managed policies (ReadOnlyAccess, S3FullAccess). "
                           "These grant more permissions than typically needed.",
                action="Use AWS Access Analyzer to identify actual permissions used, "
                      "then create custom policies with only those permissions.",
                effort="significant",
                impact="medium",
                affected_identities=[{"id": str(i.id), "name": i.name} for i in broad_roles[:10]],
                cli_command="aws accessanalyzer generate-policy --principal-arn ROLE_ARN",
            ))

        return recs

    async def _recommend_add_monitoring(self, session, identities: list[Identity]) -> list[Recommendation]:
        """Recommend adding monitoring for high-risk identities."""
        recs = []
        high_risk = [i for i in identities if i.risk_score >= 35]

        if high_risk:
            recs.append(Recommendation(
                id="REC-005",
                priority="medium",
                title="Enable CloudTrail monitoring for high-risk identities",
                description=f"{len(high_risk)} identities have risk scores >= 35. "
                           f"These should have enhanced monitoring to detect misuse.",
                action="Create CloudWatch alarms on CloudTrail events for these role assumptions. "
                      "Alert on unusual activity patterns.",
                effort="moderate",
                impact="high",
                affected_identities=[{"id": str(i.id), "name": i.name} for i in high_risk[:10]],
                cli_command="aws cloudtrail create-trail --name mii-high-risk-monitoring --s3-bucket-name YOUR_BUCKET",
            ))

        return recs

    @staticmethod
    def _rec_to_dict(rec: Recommendation) -> dict:
        return {
            "id": rec.id,
            "priority": rec.priority,
            "title": rec.title,
            "description": rec.description,
            "action": rec.action,
            "effort": rec.effort,
            "impact": rec.impact,
            "affected_identities": rec.affected_identities,
            "terraform_snippet": rec.terraform_snippet,
            "cli_command": rec.cli_command,
        }
