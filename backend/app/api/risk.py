"""Risk scoring API endpoints."""

import math
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Identity
from app.schemas.risk import (
    RecalculateResponse,
    RiskFactorDetail,
    RiskScoreListItem,
    RiskScoreListResponse,
    RiskScoreResponse,
)
from app.services.risk_engine import RiskEngine

router = APIRouter()


@router.get("/risk/scores", response_model=RiskScoreListResponse)
async def list_risk_scores(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
    min_score: int = Query(default=0, ge=0, le=100),
    session: AsyncSession = Depends(get_session),
):
    """List all identities with their risk scores, sorted by highest risk."""
    # Count
    count_query = select(func.count()).select_from(Identity).where(Identity.risk_score >= min_score)
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Query
    query = (
        select(Identity)
        .where(Identity.risk_score >= min_score)
        .order_by(Identity.risk_score.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await session.execute(query)
    identities = result.scalars().all()

    items = [
        RiskScoreListItem(
            identity_id=i.id,
            identity_name=i.name,
            identity_type=i.type,
            source=i.source,
            score=i.risk_score,
            factor_count=len(i.risk_factors or []),
        )
        for i in identities
    ]

    return RiskScoreListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if per_page else 0,
    )


@router.get("/risk/scores/{identity_id}", response_model=RiskScoreResponse)
async def get_risk_score(
    identity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get detailed risk score breakdown for a specific identity."""
    stmt = select(Identity).where(Identity.id == identity_id)
    result = await session.execute(stmt)
    identity = result.scalar_one_or_none()

    if not identity:
        raise HTTPException(status_code=404, detail="Identity not found")

    factors = [
        RiskFactorDetail(**f)
        for f in (identity.risk_factors or [])
    ]

    return RiskScoreResponse(
        identity_id=identity.id,
        identity_name=identity.name,
        score=identity.risk_score,
        factors=factors,
        unevaluable_factors=[],
    )


@router.post("/risk/recalculate", response_model=RecalculateResponse)
async def recalculate_risk_scores(background_tasks: BackgroundTasks):
    """Trigger a full risk score recalculation for all identities."""

    async def _recalculate():
        engine = RiskEngine()
        await engine.recalculate_all()

    background_tasks.add_task(_recalculate)

    return RecalculateResponse(
        status="started",
        identities_processed=0,
        message="Risk recalculation started in background.",
    )
