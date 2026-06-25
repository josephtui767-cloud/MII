"""AI Advisor — generates natural language explanations using OpenAI-compatible API."""

import asyncio
import logging
import uuid

from openai import AsyncOpenAI

from app.config import settings
from app.database import async_session_factory
from app.models import Identity, IdentityAccess, Resource, TrustRelationship
from app.services.graph_engine import graph_engine
from sqlalchemy import select
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a security advisor explaining machine identity risks for a Machine Identity Intelligence platform.

RULES:
- You MUST ONLY reference data provided in the context below.
- You MUST NOT fabricate identity names, resource names, trust relationships, or risk scores.
- If data is missing or unavailable, state what is unavailable.
- Provide clear, actionable explanations suitable for a security review.
- Keep explanations concise but thorough — cover risk score, contributing factors, trust relationships, and accessible resources.
- Use bullet points for factor breakdowns.
- End with a brief remediation recommendation when appropriate."""

REQUEST_TIMEOUT = 30.0  # seconds


class AIAdvisor:
    """Generates natural language explanations of identity risk and trust chains."""

    def __init__(self):
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
            )
        return self._client

    async def explain_risk(self, identity_id: uuid.UUID) -> dict:
        """Generate a natural language explanation of why an identity is risky.

        Returns dict with identity_id, identity_name, explanation, risk_score, risk_factors.
        """
        async with async_session_factory() as session:
            stmt = select(Identity).where(Identity.id == identity_id)
            result = await session.execute(stmt)
            identity = result.scalar_one_or_none()

            if not identity:
                return {
                    "identity_id": identity_id,
                    "identity_name": "unknown",
                    "explanation": f"Identity with ID {identity_id} was not found in the inventory.",
                    "risk_score": 0,
                    "risk_factors": [],
                }

            # Get trusted_by
            stmt = (
                select(TrustRelationship)
                .where(TrustRelationship.target_identity_id == identity_id)
                .options(selectinload(TrustRelationship.source_identity))
            )
            result = await session.execute(stmt)
            trust_rels = result.scalars().all()

            # Get can_access
            stmt = (
                select(IdentityAccess)
                .where(IdentityAccess.identity_id == identity_id)
                .options(selectinload(IdentityAccess.resource))
            )
            result = await session.execute(stmt)
            access_records = result.scalars().all()

        # Build context for LLM
        risk_factors = identity.risk_factors or []
        trusted_by_text = self._format_trusted_by(trust_rels)
        can_access_text = self._format_can_access(access_records)

        user_prompt = f"""Explain why the following machine identity is risky:

Identity: {identity.name}
Type: {identity.type}
Source: {identity.source}
ARN: {identity.arn or 'N/A'}
Account: {identity.account_id or 'N/A'}
Last Used: {identity.last_used_at or 'Never'}
Risk Score: {identity.risk_score}/100

Risk Factors:
{self._format_risk_factors(risk_factors)}

Trusted By ({len(trust_rels)} identities):
{trusted_by_text}

Can Access ({len(access_records)} resources):
{can_access_text}

Explain why this identity is risky and what actions should be considered."""

        explanation = await self._generate(user_prompt)

        return {
            "identity_id": identity_id,
            "identity_name": identity.name,
            "explanation": explanation,
            "risk_score": identity.risk_score,
            "risk_factors": risk_factors,
        }

    async def explain_path(self, source_id: uuid.UUID, target_id: uuid.UUID) -> dict:
        """Generate natural language description of trust chain between two identities."""
        # Get identity names
        async with async_session_factory() as session:
            source = await session.get(Identity, source_id)
            target = await session.get(Identity, target_id)

        if not source:
            return {
                "source_name": "unknown",
                "target_name": target.name if target else "unknown",
                "explanation": f"Source identity with ID {source_id} was not found in the inventory.",
                "path_exists": False,
                "hop_count": None,
            }

        if not target:
            return {
                "source_name": source.name,
                "target_name": "unknown",
                "explanation": f"Target identity with ID {target_id} was not found in the inventory.",
                "path_exists": False,
                "hop_count": None,
            }

        # Find paths using graph engine
        chains = graph_engine.find_path(source_id, target_id)

        if not chains:
            return {
                "source_name": source.name,
                "target_name": target.name,
                "explanation": f"No trust path connects {source.name} to {target.name}. These identities are not linked through any trust chain.",
                "path_exists": False,
                "hop_count": None,
            }

        # Format paths for LLM
        paths_text = ""
        for i, chain in enumerate(chains[:5], 1):  # Limit to 5 paths
            path_steps = " → ".join(
                f"{step.name} ({step.type})"
                + (f" [{step.trust_type}]" if step.trust_type else "")
                for step in chain.path
            )
            paths_text += f"  Path {i} ({chain.hop_count} hops): {path_steps}\n"

        user_prompt = f"""Describe the trust chain path between these two machine identities:

Source: {source.name} ({source.type}, {source.source})
Target: {target.name} ({target.type}, {target.source})

Trust Paths Found: {len(chains)}
{paths_text}

Describe how trust flows from source to target, what each hop means for security, and what the implications are."""

        explanation = await self._generate(user_prompt)

        return {
            "source_name": source.name,
            "target_name": target.name,
            "explanation": explanation,
            "path_exists": True,
            "hop_count": chains[0].hop_count if chains else None,
        }

    async def explain_blast_radius(self, identity_id: uuid.UUID) -> dict:
        """Generate natural language summary of blast radius for an identity."""
        async with async_session_factory() as session:
            identity = await session.get(Identity, identity_id)

        if not identity:
            return {
                "identity_id": identity_id,
                "identity_name": "unknown",
                "explanation": f"Identity with ID {identity_id} was not found in the inventory.",
                "total_reachable": 0,
            }

        # Get blast radius from graph engine
        blast = graph_engine.blast_radius(identity_id)

        # Limit to 50 reachable entities for the prompt
        reachable_text = ""
        for item in blast.reachable_identities[:50]:
            reachable_text += f"  - {item['name']} ({item['type']}, risk: {item['risk_score']})\n"

        if blast.total_reachable_identities > 50:
            reachable_text += f"  ... and {blast.total_reachable_identities - 50} more\n"

        user_prompt = f"""Summarize the blast radius for this machine identity:

Identity: {identity.name} ({identity.type})
ARN: {identity.arn or 'N/A'}
Risk Score: {identity.risk_score}/100

Reachable Identities: {blast.total_reachable_identities}
{reachable_text}

Summarize what could be impacted if this identity were compromised, and the overall severity of the blast radius."""

        explanation = await self._generate(user_prompt)

        return {
            "identity_id": identity_id,
            "identity_name": identity.name,
            "explanation": explanation,
            "total_reachable": blast.total_reachable_identities,
        }

    async def generate_remediation_plan(self, identity_id: uuid.UUID) -> dict:
        """Generate a structured AI remediation plan for an identity."""
        async with async_session_factory() as session:
            stmt = select(Identity).where(Identity.id == identity_id)
            result = await session.execute(stmt)
            identity = result.scalar_one_or_none()

            if not identity:
                return {
                    "identity_id": identity_id,
                    "identity_name": "unknown",
                    "plan": "Identity not found.",
                }

            # Get trusted_by
            stmt = (
                select(TrustRelationship)
                .where(TrustRelationship.target_identity_id == identity_id)
                .options(selectinload(TrustRelationship.source_identity))
            )
            result = await session.execute(stmt)
            trust_rels = result.scalars().all()

            # Get can_access
            stmt = (
                select(IdentityAccess)
                .where(IdentityAccess.identity_id == identity_id)
                .options(selectinload(IdentityAccess.resource))
            )
            result = await session.execute(stmt)
            access_records = result.scalars().all()

        risk_factors = identity.risk_factors or []
        trusted_by_text = self._format_trusted_by(trust_rels)
        can_access_text = self._format_can_access(access_records)

        user_prompt = f"""Generate a detailed remediation plan for this machine identity:

Identity: {identity.name}
Type: {identity.type}
Source: {identity.source}
ARN: {identity.arn or 'N/A'}
Account: {identity.account_id or 'N/A'}
Last Used: {identity.last_used_at or 'Never'}
Risk Score: {identity.risk_score}/100

Risk Factors:
{self._format_risk_factors(risk_factors)}

Trusted By ({len(trust_rels)} identities):
{trusted_by_text}

Can Access ({len(access_records)} resources):
{can_access_text}

Provide a structured remediation plan with:
1. PRIORITY: Critical/High/Medium/Low
2. SUMMARY: One sentence describing what needs to change
3. STEPS: Numbered step-by-step remediation actions (3-5 steps)
4. AWS CLI COMMANDS: Ready-to-run commands to implement the fix
5. TERRAFORM CODE: Infrastructure-as-code snippet for the fix
6. IMPACT: What changes after remediation (before vs after)
7. RISK REDUCTION: How much the risk score would decrease
8. TIMELINE: Recommended timeline for implementation

Be specific to this identity. Use the actual role name and ARN in commands."""

        plan = await self._generate(user_prompt)

        return {
            "identity_id": str(identity_id),
            "identity_name": identity.name,
            "risk_score": identity.risk_score,
            "plan": plan,
        }

    async def _generate(self, user_prompt: str) -> str:
        """Call the LLM with system prompt and user prompt."""
        if not settings.OPENAI_API_KEY:
            return "AI is not available — no OpenAI API key configured."

        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.3,
                    max_tokens=1500,
                ),
                timeout=REQUEST_TIMEOUT,
            )
            return response.choices[0].message.content or "No response generated."
        except asyncio.TimeoutError:
            logger.warning("AI request timed out")
            return "AI generation timed out. Please try again."
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            return f"Unable to generate AI response: {e}"

    @staticmethod
    def _format_risk_factors(factors: list[dict]) -> str:
        if not factors:
            return "  No risk factors identified."
        lines = []
        for f in factors:
            lines.append(f"  - {f.get('factor', 'unknown')}: +{f.get('points', 0)} pts — {f.get('reason', '')}")
        return "\n".join(lines)

    @staticmethod
    def _format_trusted_by(trust_rels) -> str:
        if not trust_rels:
            return "  None"
        lines = []
        for rel in trust_rels[:20]:  # Limit context size
            source = rel.source_identity
            if source:
                lines.append(f"  - {source.name} ({source.type}) via {rel.trust_type}")
        if len(trust_rels) > 20:
            lines.append(f"  ... and {len(trust_rels) - 20} more")
        return "\n".join(lines)

    @staticmethod
    def _format_can_access(access_records) -> str:
        if not access_records:
            return "  None"
        lines = []
        for record in access_records[:20]:  # Limit context size
            resource = record.resource
            if resource:
                lines.append(
                    f"  - {resource.name} ({resource.resource_type}) — {record.access_type}"
                    + (f" [{resource.classification}]" if resource.classification != "unclassified" else "")
                )
        if len(access_records) > 20:
            lines.append(f"  ... and {len(access_records) - 20} more")
        return "\n".join(lines)


# Singleton instance
ai_advisor = AIAdvisor()
