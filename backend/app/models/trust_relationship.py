"""TrustRelationship model — directed trust edge between two identities."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TrustRelationship(Base):
    __tablename__ = "trust_relationship"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_identity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.id", ondelete="CASCADE"), nullable=False
    )
    target_identity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.id", ondelete="CASCADE"), nullable=False
    )
    trust_type: Mapped[str] = mapped_column(String(64), nullable=False)
    external_account_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    conditions: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    source_identity = relationship(
        "Identity", foreign_keys=[source_identity_id], back_populates="trusts_given"
    )
    target_identity = relationship(
        "Identity", foreign_keys=[target_identity_id], back_populates="trusts_received"
    )

    __table_args__ = (
        UniqueConstraint("source_identity_id", "target_identity_id", "trust_type", name="uq_trust_relationship"),
        CheckConstraint(
            "trust_type IN ('OIDC_Federation', 'AssumeRole', 'Cross_Account_Trust', 'Pipeline_Assume')",
            name="ck_trust_type",
        ),
    )

    def __repr__(self) -> str:
        return f"<TrustRelationship(source={self.source_identity_id}, target={self.target_identity_id}, type={self.trust_type!r})>"
