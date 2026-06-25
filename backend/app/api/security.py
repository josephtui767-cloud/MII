"""Security API endpoints — findings, compliance, recommendations, executive summary."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Identity, TrustRelationship
from app.services.findings_engine import FindingsEngine

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/security/findings")
async def get_findings():
    """Get all security findings with severity, remediation, and blast radius."""
    engine = FindingsEngine()
    findings = await engine.generate_findings()

    critical = sum(1 for f in findings if f["severity"] == "critical")
    high = sum(1 for f in findings if f["severity"] == "high")
    medium = sum(1 for f in findings if f["severity"] == "medium")
    low = sum(1 for f in findings if f["severity"] == "low")

    return {
        "total": len(findings),
        "summary": {"critical": critical, "high": high, "medium": medium, "low": low},
        "findings": findings,
    }


@router.get("/security/compliance")
async def get_compliance():
    """Run compliance checks and return pass/fail results."""
    try:
        from app.services.compliance_engine import ComplianceEngine
        engine = ComplianceEngine()
        result = await engine.run_all_checks()
        return result
    except Exception as e:
        logger.error(f"Compliance check failed: {e}", exc_info=True)
        return {
            "compliance_score": 0,
            "total_checks": 0,
            "passing": 0,
            "failing": 0,
            "warnings": 0,
            "checks": [],
            "error": str(e),
        }


@router.get("/security/recommendations")
async def get_recommendations():
    """Get prioritized security recommendations with remediation steps."""
    try:
        from app.services.recommendations_engine import RecommendationsEngine
        engine = RecommendationsEngine()
        recommendations = await engine.generate_recommendations()
        return {"total": len(recommendations), "recommendations": recommendations}
    except Exception as e:
        logger.error(f"Recommendations failed: {e}", exc_info=True)
        return {"total": 0, "recommendations": [], "error": str(e)}


@router.get("/security/trust-debt")
async def get_trust_debt():
    """Calculate trust debt score — accumulated unnecessary trust relationships."""
    try:
        from app.services.trust_debt_engine import TrustDebtEngine
        engine = TrustDebtEngine()
        result = await engine.calculate_trust_debt()
        return result
    except Exception as e:
        logger.error(f"Trust debt calculation failed: {e}", exc_info=True)
        return {"total_debt_score": 0, "debt_grade": "?", "debt_items": [], "error": str(e)}


@router.get("/security/blast-path/{identity_id}")
async def get_blast_path(identity_id: str):
    """Simulate blast path from a compromised identity."""
    try:
        from app.services.blast_path_engine import BlastPathEngine
        import uuid
        engine = BlastPathEngine()
        result = await engine.simulate(uuid.UUID(identity_id))
        return result
    except Exception as e:
        logger.error(f"Blast path simulation failed: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/security/blast-path-gitlab")
async def get_blast_path_gitlab():
    """Simulate blast path starting from GitLab CI/CD compromise."""
    try:
        from app.services.blast_path_engine import BlastPathEngine
        engine = BlastPathEngine()
        result = await engine.simulate_from_gitlab()
        return result
    except Exception as e:
        logger.error(f"Blast path GitLab simulation failed: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/security/executive-summary")
async def get_executive_summary(session: AsyncSession = Depends(get_session)):
    """Executive dashboard summary with key metrics and top actions."""
    try:
        # Total identities
        total_result = await session.execute(select(func.count()).select_from(Identity))
        total_identities = total_result.scalar() or 0

        # Risk breakdown
        high_risk_result = await session.execute(
            select(func.count()).select_from(Identity).where(Identity.risk_score >= 35)
        )
        high_risk_count = high_risk_result.scalar() or 0

        critical_risk_result = await session.execute(
            select(func.count()).select_from(Identity).where(Identity.risk_score >= 60)
        )
        critical_risk_count = critical_risk_result.scalar() or 0

        # Unused identities
        unused_result = await session.execute(
            select(func.count()).select_from(Identity).where(Identity.last_used_at.is_(None))
        )
        unused_count = unused_result.scalar() or 0

        # Trust relationships
        trust_result = await session.execute(select(func.count()).select_from(TrustRelationship))
        trust_count = trust_result.scalar() or 0

        # OIDC trust count
        oidc_result = await session.execute(
            select(func.count()).select_from(TrustRelationship).where(
                TrustRelationship.trust_type == "OIDC_Federation"
            )
        )
        oidc_count = oidc_result.scalar() or 0

        # Average risk score
        avg_result = await session.execute(select(func.avg(Identity.risk_score)))
        avg_risk = round(avg_result.scalar() or 0, 1)

        # Generate findings for summary
        try:
            findings_engine = FindingsEngine()
            findings = await findings_engine.generate_findings()
            critical_findings = sum(1 for f in findings if f["severity"] == "critical")
            high_findings = sum(1 for f in findings if f["severity"] == "high")
        except Exception:
            findings = []
            critical_findings = 0
            high_findings = 0

        # Compliance score
        compliance_score = 0
        try:
            from app.services.compliance_engine import ComplianceEngine
            compliance_engine = ComplianceEngine()
            compliance = await compliance_engine.run_all_checks()
            compliance_score = compliance.get("compliance_score", 0)
        except Exception:
            pass

        return {
            "metrics": {
                "total_identities": total_identities,
                "high_risk_identities": high_risk_count,
                "critical_risk_identities": critical_risk_count,
                "unused_identities": unused_count,
                "trust_relationships": trust_count,
                "oidc_federations": oidc_count,
                "average_risk_score": avg_risk,
                "compliance_score": compliance_score,
            },
            "risk_summary": {
                "critical_findings": critical_findings,
                "high_findings": high_findings,
                "total_findings": len(findings),
            },
            "top_actions": [f["title"] for f in findings if f["severity"] == "critical"][:5],
            "health_status": "critical" if critical_findings > 5 else ("warning" if critical_findings > 0 or high_findings > 3 else "healthy"),
        }
    except Exception as e:
        logger.error(f"Executive summary failed: {e}", exc_info=True)
        return {
            "metrics": {
                "total_identities": 0, "high_risk_identities": 0, "critical_risk_identities": 0,
                "unused_identities": 0, "trust_relationships": 0, "oidc_federations": 0,
                "average_risk_score": 0, "compliance_score": 0,
            },
            "risk_summary": {"critical_findings": 0, "high_findings": 0, "total_findings": 0},
            "top_actions": [],
            "health_status": "unknown",
            "error": str(e),
        }
