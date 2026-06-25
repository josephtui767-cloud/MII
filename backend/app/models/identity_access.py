"""IdentityAccess model — links an identity to a resource with an access type."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class IdentityAccess(Base):
    __tablename__ = "identity_access"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.id", ondelete="CASCADE"), nullable=False
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resource.id", ondelete="CASCADE"), nullable=False
    )
    access_type: Mapped[str] = mapped_column(String(128), nullable=False)
    actions: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    identity = relationship("Identity", back_populates="access_records")
    resource = relationship("Resource", back_populates="access_records")

    __table_args__ = (
        UniqueConstraint("identity_id", "resource_id", "access_type", name="uq_identity_access"),
        CheckConstraint("access_type IN ('Read', 'Write', 'Admin')", name="ck_access_type"),
    )

    def __repr__(self) -> str:
        return f"<IdentityAccess(identity={self.identity_id}, resource={self.resource_id}, type={self.access_type!r})>"
