"""Report download API endpoints — PDF, Markdown, and Excel exports for each tab."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Identity
from app.services.report_engine import ReportEngine

router = APIRouter()
logger = logging.getLogger(__name__)

CONTENT_TYPES = {
    "pdf": "application/pdf",
    "markdown": "text/markdown",
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

EXTENSIONS = {
    "pdf": "pdf",
    "markdown": "md",
    "excel": "xlsx",
}


def _file_response(content: bytes | str, filename: str, format: str) -> Response:
    """Create a downloadable file response."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return Response(
        content=content,
        media_type=CONTENT_TYPES[format],
        headers={"Content-Disposition": f'attachment; filename="{filename}.{EXTENSIONS[format]}"'},
    )


@router.get("/reports/identities")
async def export_identities(
    format: str = Query(default="pdf", regex="^(pdf|markdown|excel)$"),
    session: AsyncSession = Depends(get_session),
):
    """Export identity inventory report."""
    try:
        stmt = select(Identity).order_by(Identity.risk_score.desc())
        result = await session.execute(stmt)
        identities = result.scalars().all()

        data = [
            {
                "name": i.name,
                "type": i.type,
                "source": i.source,
                "risk_score": i.risk_score,
                "last_used": str(i.last_used_at.date()) if i.last_used_at else "Never",
                "trust_count": len(i.metadata_.get("trust_relationships", [])) if i.metadata_ else 0,
            }
            for i in identities
        ]

        engine = ReportEngine()
        if format == "pdf":
            content = engine.generate_identities_pdf(data)
        elif format == "markdown":
            content = engine.generate_identities_markdown(data)
        else:
            content = engine.generate_identities_excel(data)

        return _file_response(content, "mii-identities-report", format)
    except Exception as e:
        logger.error(f"Identity report generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@router.get("/reports/findings")
async def export_findings(
    format: str = Query(default="pdf", regex="^(pdf|markdown|excel)$"),
):
    """Export security findings report."""
    try:
        from app.services.findings_engine import FindingsEngine
        findings_engine = FindingsEngine()
        findings = await findings_engine.generate_findings()

        critical = sum(1 for f in findings if f["severity"] == "critical")
        high = sum(1 for f in findings if f["severity"] == "high")
        medium = sum(1 for f in findings if f["severity"] == "medium")
        low = sum(1 for f in findings if f["severity"] == "low")

        data = {
            "total": len(findings),
            "summary": {"critical": critical, "high": high, "medium": medium, "low": low},
            "findings": findings,
        }

        engine = ReportEngine()
        if format == "pdf":
            content = engine.generate_findings_pdf(data)
        elif format == "markdown":
            content = engine.generate_findings_markdown(data)
        else:
            content = engine.generate_findings_excel(data)

        return _file_response(content, "mii-findings-report", format)
    except Exception as e:
        logger.error(f"Findings report generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@router.get("/reports/compliance")
async def export_compliance(
    format: str = Query(default="pdf", regex="^(pdf|markdown|excel)$"),
):
    """Export compliance report."""
    try:
        from app.services.compliance_engine import ComplianceEngine
        compliance_engine = ComplianceEngine()
        data = await compliance_engine.run_all_checks()

        engine = ReportEngine()
        if format == "pdf":
            content = engine.generate_compliance_pdf(data)
        elif format == "markdown":
            content = engine.generate_compliance_markdown(data)
        else:
            content = engine.generate_compliance_excel(data)

        return _file_response(content, "mii-compliance-report", format)
    except Exception as e:
        logger.error(f"Compliance report generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@router.get("/reports/trust-debt")
async def export_trust_debt(
    format: str = Query(default="pdf", regex="^(pdf|markdown|excel)$"),
):
    """Export trust debt report."""
    try:
        from app.services.trust_debt_engine import TrustDebtEngine
        debt_engine = TrustDebtEngine()
        data = await debt_engine.calculate_trust_debt()

        engine = ReportEngine()
        if format == "pdf":
            content = engine.generate_trust_debt_pdf(data)
        elif format == "markdown":
            content = engine.generate_trust_debt_markdown(data)
        else:
            content = engine.generate_trust_debt_excel(data)

        return _file_response(content, "mii-trust-debt-report", format)
    except Exception as e:
        logger.error(f"Trust debt report generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@router.get("/reports/blast-path/{identity_id}")
async def export_blast_path(
    identity_id: str,
    format: str = Query(default="pdf", regex="^(pdf|markdown|excel)$"),
):
    """Export blast path simulation report for a specific identity."""
    try:
        from app.services.blast_path_engine import BlastPathEngine
        blast_engine = BlastPathEngine()
        data = await blast_engine.simulate(uuid.UUID(identity_id))

        engine = ReportEngine()
        if format == "pdf":
            content = engine.generate_blast_path_pdf(data)
        elif format == "markdown":
            content = engine.generate_blast_path_markdown(data)
        else:
            content = engine.generate_blast_path_excel(data)

        return _file_response(content, f"mii-blast-path-{identity_id[:8]}", format)
    except Exception as e:
        logger.error(f"Blast path report generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")
