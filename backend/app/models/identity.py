"""Identity model — represents a machine identity (AWS IAM Role, GitLab tokens, etc.)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Identity(Base):
    __tablename__ = "identity"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    arn: Mapped[str | None] = mapped_column(String(2048), unique=True, nullable=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    owner: Mapped[str | None] = mapped_column(String(256), nullable=True)
    account_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    risk_factors: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    trusts_given = relationship(
        "TrustRelationship",
        foreign_keys="TrustRelationship.source_identity_id",
        back_populates="source_identity",
        cascade="all, delete-orphan",
    )
    trusts_received = relationship(
        "TrustRelationship",
        foreign_keys="TrustRelationship.target_identity_id",
        back_populates="target_identity",
        cascade="all, delete-orphan",
    )
    access_records = relationship(
        "IdentityAccess",
        back_populates="identity",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "type IN ('AWS_IAM_Role', 'GitLab_Project_Access_Token', 'GitLab_Group_Access_Token', 'GitLab_Runner')",
            name="ck_identity_type",
        ),
        CheckConstraint("source IN ('AWS', 'GitLab')", name="ck_identity_source"),
        CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="ck_identity_risk_score"),
    )

    def __repr__(self) -> str:
        return f"<Identity(name={self.name!r}, type={self.type!r}, source={self.source!r})>"
