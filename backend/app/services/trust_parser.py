"""Trust Relationship Parser — extracts trust relationships from AWS trust policies and GitLab configs."""

import json
import logging
import re
import uuid
from datetime import datetime

from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import async_session_factory
from app.models import Identity, TrustRelationship

logger = logging.getLogger(__name__)

# Pattern to extract AWS account ID from an ARN
ARN_ACCOUNT_PATTERN = re.compile(r"arn:aws[^:]*:[^:]*:(?:[^:]*):(\d{12}):")
# Pattern to match a bare account ID (root principal)
ACCOUNT_ROOT_PATTERN = re.compile(r"arn:aws:iam::(\d{12}):root")
# GitLab OIDC provider patterns
GITLAB_OIDC_PATTERNS = [
    "gitlab.com",
    "gitlab",
    "oidc.gitlab",
]


class TrustParser:
    """Parses trust policies and creates TrustRelationship records."""

    def __init__(self):
        self.relationships_created = 0
        self.relationships_removed = 0
        self.errors: list[str] = []

    async def parse_all_identities(self) -> dict:
        """Parse trust policies for all AWS identities in the database.

        Returns summary with counts.
        """
        self.relationships_created = 0
        self.relationships_removed = 0
        self.errors = []

        async with async_session_factory() as session:
            # Get all AWS IAM roles (they have trust policies)
            stmt = select(Identity).where(
                Identity.type == "AWS_IAM_Role",
                Identity.is_resolved == True,
            )
            result = await session.execute(stmt)
            identities = result.scalars().all()

            logger.info(f"Parsing trust policies for {len(identities)} AWS IAM roles")

            for identity in identities:
                try:
                    await self._parse_identity_trust_policy(session, identity)
                except Exception as e:
                    error_msg = f"Error parsing trust policy for {identity.arn}: {e}"
                    logger.warning(error_msg)
                    self.errors.append(error_msg)

            await session.commit()

        return {
            "relationships_created": self.relationships_created,
            "relationships_removed": self.relationships_removed,
            "errors": self.errors,
        }

    async def _parse_identity_trust_policy(self, session, identity: Identity):
        """Parse a single identity's trust policy and create/update relationships."""
        metadata = identity.metadata_ or {}
        trust_policy = metadata.get("trust_policy")

        if not trust_policy:
            return

        # Validate trust policy is parseable
        if isinstance(trust_policy, str):
            try:
                trust_policy = json.loads(trust_policy)
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON in trust policy for {identity.arn}: {e}"
                logger.warning(error_msg)
                self.errors.append(error_msg)
                return

        # Track which relationships we find in this scan
        found_relationships: set[tuple[uuid.UUID, str]] = set()

        statements = trust_policy.get("Statement", [])
        for statement in statements:
            if statement.get("Effect") != "Allow":
                continue

            principal = statement.get("Principal", {})
            conditions = statement.get("Condition", {})

            # Handle string principal (e.g., "*")
            if isinstance(principal, str):
                if principal == "*":
                    # Wildcard trust — note but don't create specific relationships
                    logger.debug(f"Wildcard trust on {identity.arn}")
                continue

            # Check for OIDC Federation (GitLab)
            federated = principal.get("Federated")
            if federated:
                await self._handle_federated_principal(
                    session, identity, federated, conditions, found_relationships
                )

            # Check for AWS principals
            aws_principals = principal.get("AWS")
            if aws_principals:
                if isinstance(aws_principals, str):
                    aws_principals = [aws_principals]
                for arn in aws_principals:
                    await self._handle_aws_principal(
                        session, identity, arn, conditions, found_relationships
                    )

            # Check for Service principals (not creating trust relationships for these
            # as they are AWS service-to-service, not machine identity trust)

        # Remove relationships that no longer exist in the trust policy
        await self._remove_stale_relationships(session, identity.id, found_relationships)

    async def _handle_federated_principal(
        self,
        session,
        target_identity: Identity,
        federated_arn: str | list,
        conditions: dict,
        found_relationships: set,
    ):
        """Handle Federated principal — check for GitLab OIDC."""
        if isinstance(federated_arn, list):
            for arn in federated_arn:
                await self._handle_federated_principal(
                    session, target_identity, arn, conditions, found_relationships
                )
            return

        # Check if this is a GitLab OIDC provider
        is_gitlab = any(pattern in federated_arn.lower() for pattern in GITLAB_OIDC_PATTERNS)

        if is_gitlab:
            # Find or create a GitLab identity representing the OIDC trust source
            source_identity = await self._find_or_create_gitlab_oidc_identity(
                session, federated_arn, conditions
            )

            # Create OIDC_Federation relationship
            rel = await self._create_relationship(
                session,
                source_identity_id=source_identity.id,
                target_identity_id=target_identity.id,
                trust_type="OIDC_Federation",
                conditions=conditions,
            )
            if rel:
                found_relationships.add((source_identity.id, "OIDC_Federation"))

    async def _handle_aws_principal(
        self,
        session,
        target_identity: Identity,
        principal_arn: str,
        conditions: dict,
        found_relationships: set,
    ):
        """Handle AWS principal — determine if cross-account or same-account."""
        if principal_arn == "*":
            return  # Wildcard — skip

        # Extract account ID from the principal ARN
        principal_account_id = self._extract_account_id(principal_arn)
        target_account_id = target_identity.account_id

        # Find or create the source identity
        source_identity = await self._find_or_create_aws_identity(session, principal_arn)

        # Determine trust type
        if principal_account_id and target_account_id and principal_account_id != target_account_id:
            trust_type = "Cross_Account_Trust"
            external_account_id = principal_account_id
        else:
            trust_type = "AssumeRole"
            external_account_id = None

        rel = await self._create_relationship(
            session,
            source_identity_id=source_identity.id,
            target_identity_id=target_identity.id,
            trust_type=trust_type,
            conditions=conditions,
            external_account_id=external_account_id,
        )
        if rel:
            found_relationships.add((source_identity.id, trust_type))

    async def _find_or_create_gitlab_oidc_identity(
        self, session, provider_arn: str, conditions: dict
    ) -> Identity:
        """Find existing GitLab OIDC identity or create a placeholder."""
        # Use the provider ARN as a unique identifier
        oidc_arn = f"gitlab:oidc:{provider_arn}"

        stmt = select(Identity).where(Identity.arn == oidc_arn)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return existing

        # Extract project/group info from conditions if available
        name = "GitLab OIDC"
        sub_condition = conditions.get("StringEquals", {}).get(
            "token.actions.githubusercontent.com:sub",
            conditions.get("StringLike", {}).get("gitlab.com:sub", ""),
        )
        if sub_condition:
            name = f"GitLab OIDC ({sub_condition})"

        new_identity = Identity(
            name=name,
            arn=oidc_arn,
            type="GitLab_Runner",
            source="GitLab",
            is_resolved=False,  # Placeholder until matched with actual GitLab identity
            metadata_={
                "oidc_provider": provider_arn,
                "conditions": conditions,
            },
        )
        session.add(new_identity)
        await session.flush()
        return new_identity

    async def _find_or_create_aws_identity(self, session, arn: str) -> Identity:
        """Find existing AWS identity by ARN or create unresolved placeholder."""
        stmt = select(Identity).where(Identity.arn == arn)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return existing

        # Create placeholder
        account_id = self._extract_account_id(arn)
        # Extract a readable name from the ARN
        name = arn.split("/")[-1] if "/" in arn else arn.split(":")[-1]

        new_identity = Identity(
            name=name,
            arn=arn,
            type="AWS_IAM_Role",
            source="AWS",
            account_id=account_id,
            is_resolved=False,  # Will be resolved on next discovery scan
            metadata_={"placeholder": True},
        )
        session.add(new_identity)
        await session.flush()
        return new_identity

    async def _create_relationship(
        self,
        session,
        source_identity_id: uuid.UUID,
        target_identity_id: uuid.UUID,
        trust_type: str,
        conditions: dict | None = None,
        external_account_id: str | None = None,
    ) -> TrustRelationship | None:
        """Create or update a trust relationship (upsert)."""
        try:
            # Check if exists
            stmt = select(TrustRelationship).where(
                TrustRelationship.source_identity_id == source_identity_id,
                TrustRelationship.target_identity_id == target_identity_id,
                TrustRelationship.trust_type == trust_type,
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Update conditions if changed
                existing.conditions = conditions or {}
                existing.external_account_id = external_account_id
                return existing
            else:
                new_rel = TrustRelationship(
                    source_identity_id=source_identity_id,
                    target_identity_id=target_identity_id,
                    trust_type=trust_type,
                    conditions=conditions or {},
                    external_account_id=external_account_id,
                )
                session.add(new_rel)
                await session.flush()
                self.relationships_created += 1
                return new_rel
        except Exception as e:
            logger.warning(f"Failed to create relationship: {e}")
            return None

    async def _remove_stale_relationships(
        self,
        session,
        target_identity_id: uuid.UUID,
        found_relationships: set[tuple[uuid.UUID, str]],
    ):
        """Remove relationships that no longer exist in the trust policy."""
        # Get all existing relationships targeting this identity
        stmt = select(TrustRelationship).where(
            TrustRelationship.target_identity_id == target_identity_id
        )
        result = await session.execute(stmt)
        existing_rels = result.scalars().all()

        for rel in existing_rels:
            key = (rel.source_identity_id, rel.trust_type)
            if key not in found_relationships:
                await session.delete(rel)
                self.relationships_removed += 1

    @staticmethod
    def _extract_account_id(arn: str) -> str | None:
        """Extract AWS account ID from an ARN."""
        # Match standard ARN format
        match = ARN_ACCOUNT_PATTERN.search(arn)
        if match:
            return match.group(1)

        # Match root principal
        match = ACCOUNT_ROOT_PATTERN.search(arn)
        if match:
            return match.group(1)

        # Try splitting ARN directly
        parts = arn.split(":")
        if len(parts) >= 5 and parts[4].isdigit() and len(parts[4]) == 12:
            return parts[4]

        # Might be just an account ID
        if arn.isdigit() and len(arn) == 12:
            return arn

        return None
