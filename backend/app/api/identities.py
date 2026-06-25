"""Identity API endpoints — list, filter, and detail views."""

import math
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.models import Identity, IdentityAccess, TrustRelationship
from app.schemas.identity import (
    CanAccessSchema,
    IdentityDetailResponse,
    IdentityListResponse,
    IdentityResponse,
    RiskFactorSchema,
    TrustedBySchema,
)

router = APIRouter()


@router.get("/identities", response_model=IdentityListResponse)
async def list_identities(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
    type: str | None = None,
    source: str | None = None,
    min_risk_score: int | None = Query(default=None, ge=0, le=100),
    has_admin: bool | None = None,
    has_production_access: bool | None = None,
    unused_days: int | None = Query(default=None, ge=1),
    trusted_by_gitlab: bool | None = None,
    cross_account: bool | None = None,
    sort_by: str = "risk_score",
    sort_order: str = "desc",
    session: AsyncSession = Depends(get_session),
):
    """List identities with pagination and filtering."""
    # Base query
    query = select(Identity)
    count_query = select(func.count()).select_from(Identity)

    # Apply filters
    filters = []

    if type:
        filters.append(Identity.type == type)
    if source:
        filters.append(Identity.source == source)
    if min_risk_score is not None:
        filters.append(Identity.risk_score >= min_risk_score)

    if unused_days is not None:
        threshold = datetime.now(timezone.utc) - timedelta(days=unused_days)
        filters.append(
            or_(
                Identity.last_used_at < threshold,
                Identity.last_used_at.is_(None),
            )
        )

    if has_admin is True:
        # Filter identities where risk_factors contains admin_permissions
        filters.append(
            Identity.risk_factors.cast(str).contains("admin_permissions")
        )

    if has_production_access is True:
        filters.append(
            Identity.risk_factors.cast(str).contains("production_access")
        )

    if cross_account is True:
        filters.append(
            Identity.risk_factors.cast(str).contains("cross_account_access")
        )

    if trusted_by_gitlab is True:
        # Subquery: identities that have incoming OIDC_Federation or Pipeline_Assume trust
        subq = (
            select(TrustRelationship.target_identity_id)
            .where(TrustRelationship.trust_type.in_(["OIDC_Federation", "Pipeline_Assume"]))
            .distinct()
        )
        filters.append(Identity.id.in_(subq))

    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))

    # Get total count
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Apply sorting
    sort_column = getattr(Identity, sort_by, Identity.risk_score)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Apply pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await session.execute(query)
    identities = result.scalars().all()

    # Build response
    items = [
        IdentityResponse(
            id=i.id,
            name=i.name,
            arn=i.arn,
            type=i.type,
            source=i.source,
            owner=i.owner,
            account_id=i.account_id,
            last_used_at=i.last_used_at,
            risk_score=i.risk_score,
            risk_factors=[RiskFactorSchema(**f) for f in (i.risk_factors or [])],
            created_at=i.created_at,
        )
        for i in identities
    ]

    return IdentityListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if per_page else 0,
    )


@router.get("/identities/{identity_id}", response_model=IdentityDetailResponse)
async def get_identity_detail(
    identity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get detailed information about a specific identity."""
    # Get identity
    stmt = select(Identity).where(Identity.id == identity_id)
    result = await session.execute(stmt)
    identity = result.scalar_one_or_none()

    if not identity:
        raise HTTPException(status_code=404, detail="Identity not found")

    # Get trusted_by (incoming trust relationships)
    stmt = (
        select(TrustRelationship)
        .where(TrustRelationship.target_identity_id == identity_id)
        .options(selectinload(TrustRelationship.source_identity))
    )
    result = await session.execute(stmt)
    trust_rels = result.scalars().all()

    trusted_by = [
        TrustedBySchema(
            id=rel.source_identity.id,
            name=rel.source_identity.name,
            type=rel.source_identity.type,
            trust_type=rel.trust_type,
        )
        for rel in trust_rels
        if rel.source_identity
    ]

    # Get can_access (resource access)
    stmt = (
        select(IdentityAccess)
        .where(IdentityAccess.identity_id == identity_id)
        .options(selectinload(IdentityAccess.resource))
    )
    result = await session.execute(stmt)
    access_records = result.scalars().all()

    can_access = [
        CanAccessSchema(
            id=record.resource.id,
            name=record.resource.name,
            resource_type=record.resource.resource_type,
            access_type=record.access_type,
            classification=record.resource.classification,
        )
        for record in access_records
        if record.resource
    ]

    return IdentityDetailResponse(
        id=identity.id,
        name=identity.name,
        arn=identity.arn,
        type=identity.type,
        source=identity.source,
        owner=identity.owner,
        account_id=identity.account_id,
        last_used_at=identity.last_used_at,
        is_resolved=identity.is_resolved,
        risk_score=identity.risk_score,
        risk_factors=[RiskFactorSchema(**f) for f in (identity.risk_factors or [])],
        trusted_by=trusted_by,
        can_access=can_access,
        created_at=identity.created_at,
    )
