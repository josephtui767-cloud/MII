"""AI Advisor API endpoints — natural language explanations."""

from fastapi import APIRouter

from app.schemas.ai import (
    BlastRadiusExplainRequest,
    BlastRadiusExplainResponse,
    ExplainPathRequest,
    ExplainPathResponse,
    ExplainRiskRequest,
    ExplainRiskResponse,
)
from app.schemas.risk import RiskFactorDetail
from app.services.ai_advisor import ai_advisor

router = APIRouter()


@router.post("/ai/explain-risk", response_model=ExplainRiskResponse)
async def explain_risk(request: ExplainRiskRequest):
    """Generate a natural language explanation of why an identity is risky."""
    result = await ai_advisor.explain_risk(request.identity_id)

    return ExplainRiskResponse(
        identity_id=result["identity_id"],
        identity_name=result["identity_name"],
        explanation=result["explanation"],
        risk_score=result["risk_score"],
        risk_factors=[
            RiskFactorDetail(**f) for f in result.get("risk_factors", [])
        ],
    )


@router.post("/ai/remediation-plan")
async def generate_remediation_plan(request: ExplainRiskRequest):
    """Generate an AI-powered remediation plan with steps, commands, and Terraform code."""
    result = await ai_advisor.generate_remediation_plan(request.identity_id)
    return result


@router.post("/ai/explain-path", response_model=ExplainPathResponse)
async def explain_path(request: ExplainPathRequest):
    """Generate a natural language description of trust chain between two identities."""
    result = await ai_advisor.explain_path(request.source_identity_id, request.target_identity_id)

    return ExplainPathResponse(
        source_name=result["source_name"],
        target_name=result["target_name"],
        explanation=result["explanation"],
        path_exists=result["path_exists"],
        hop_count=result.get("hop_count"),
    )


@router.post("/ai/blast-radius", response_model=BlastRadiusExplainResponse)
async def explain_blast_radius(request: BlastRadiusExplainRequest):
    """Generate a natural language summary of blast radius for an identity."""
    result = await ai_advisor.explain_blast_radius(request.identity_id)

    return BlastRadiusExplainResponse(
        identity_id=result["identity_id"],
        identity_name=result["identity_name"],
        explanation=result["explanation"],
        total_reachable=result["total_reachable"],
    )
