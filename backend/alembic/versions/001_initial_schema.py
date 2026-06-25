"""Initial schema - identity, trust_relationship, resource, identity_access tables.

Revision ID: 001
Revises: None
Create Date: 2026-06-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Identity table
    op.create_table(
        "identity",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("arn", sa.String(2048), unique=True, nullable=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("owner", sa.String(256), nullable=True),
        sa.Column("account_id", sa.String(64), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_resolved", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("metadata", JSONB, server_default=sa.text("'{}'")),
        sa.Column("risk_score", sa.Integer(), server_default=sa.text("0")),
        sa.Column("risk_factors", JSONB, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "type IN ('AWS_IAM_Role', 'GitLab_Project_Access_Token', 'GitLab_Group_Access_Token', 'GitLab_Runner')",
            name="ck_identity_type",
        ),
        sa.CheckConstraint("source IN ('AWS', 'GitLab')", name="ck_identity_source"),
        sa.CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="ck_identity_risk_score"),
    )
    op.create_index("idx_identity_type", "identity", ["type"])
    op.create_index("idx_identity_source", "identity", ["source"])
    op.create_index("idx_identity_risk_score", "identity", [sa.text("risk_score DESC")])
    op.create_index("idx_identity_account_id", "identity", ["account_id"])
    op.create_index("idx_identity_last_used_at", "identity", ["last_used_at"])

    # Resource table
    op.create_table(
        "resource",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("arn", sa.String(2048), nullable=True),
        sa.Column("resource_type", sa.String(128), nullable=False),
        sa.Column("classification", sa.String(64), server_default=sa.text("'unclassified'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_resource_type", "resource", ["resource_type"])
    op.create_index("idx_resource_classification", "resource", ["classification"])

    # Trust relationship table
    op.create_table(
        "trust_relationship",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_identity_id", UUID(as_uuid=True), sa.ForeignKey("identity.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_identity_id", UUID(as_uuid=True), sa.ForeignKey("identity.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trust_type", sa.String(64), nullable=False),
        sa.Column("external_account_id", sa.String(64), nullable=True),
        sa.Column("conditions", JSONB, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("source_identity_id", "target_identity_id", "trust_type", name="uq_trust_relationship"),
        sa.CheckConstraint(
            "trust_type IN ('OIDC_Federation', 'AssumeRole', 'Cross_Account_Trust', 'Pipeline_Assume')",
            name="ck_trust_type",
        ),
    )
    op.create_index("idx_trust_source", "trust_relationship", ["source_identity_id"])
    op.create_index("idx_trust_target", "trust_relationship", ["target_identity_id"])
    op.create_index("idx_trust_type", "trust_relationship", ["trust_type"])

    # Identity access table
    op.create_table(
        "identity_access",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("identity_id", UUID(as_uuid=True), sa.ForeignKey("identity.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_id", UUID(as_uuid=True), sa.ForeignKey("resource.id", ondelete="CASCADE"), nullable=False),
        sa.Column("access_type", sa.String(128), nullable=False),
        sa.Column("actions", JSONB, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("identity_id", "resource_id", "access_type", name="uq_identity_access"),
        sa.CheckConstraint("access_type IN ('Read', 'Write', 'Admin')", name="ck_access_type"),
    )
    op.create_index("idx_access_identity", "identity_access", ["identity_id"])
    op.create_index("idx_access_resource", "identity_access", ["resource_id"])
    op.create_index("idx_access_type", "identity_access", ["access_type"])


def downgrade() -> None:
    op.drop_table("identity_access")
    op.drop_table("trust_relationship")
    op.drop_table("resource")
    op.drop_table("identity")
