"""Resource Access Mapper — extracts resource access from IAM policies and creates Resource/IdentityAccess records."""

import logging
import re
import uuid

from sqlalchemy import select

from app.database import async_session_factory
from app.models import Identity, IdentityAccess, Resource

logger = logging.getLogger(__name__)

# Service namespace to resource type mapping
SERVICE_RESOURCE_TYPE_MAP = {
    "s3": "S3_Bucket",
    "ec2": "EC2_Instance",
    "rds": "RDS_Database",
    "lambda": "Lambda_Function",
    "dynamodb": "DynamoDB_Table",
    "sqs": "SQS_Queue",
    "sns": "SNS_Topic",
    "ecs": "ECS_Service",
    "eks": "EKS_Cluster",
    "secretsmanager": "SecretsManager_Secret",
    "kms": "KMS_Key",
    "iam": "IAM_Resource",
    "sts": "STS_Resource",
    "logs": "CloudWatch_Logs",
    "cloudformation": "CloudFormation_Stack",
    "ecr": "ECR_Repository",
    "elasticache": "ElastiCache_Cluster",
    "es": "Elasticsearch_Domain",
    "opensearch": "OpenSearch_Domain",
    "kinesis": "Kinesis_Stream",
    "firehose": "Firehose_Stream",
    "glue": "Glue_Resource",
    "athena": "Athena_Resource",
    "redshift": "Redshift_Cluster",
    "apigateway": "API_Gateway",
    "execute-api": "API_Gateway",
    "states": "StepFunctions_StateMachine",
    "events": "EventBridge_Rule",
    "ssm": "SSM_Parameter",
}

# Actions that indicate read-only access
READ_ACTION_PATTERNS = [
    r"^.+:Get.*$",
    r"^.+:List.*$",
    r"^.+:Describe.*$",
    r"^.+:Head.*$",
    r"^.+:Query$",
    r"^.+:Scan$",
    r"^.+:Select$",
    r"^.+:Lookup.*$",
    r"^.+:Read.*$",
    r"^.+:Batch(Get|Read).*$",
]

# Actions that indicate admin/full access
ADMIN_ACTION_PATTERNS = [
    r"^\*$",
    r"^.+:\*$",
    r"^iam:.*$",
    r"^.+:Admin.*$",
]

# Well-known admin policies
ADMIN_POLICY_NAMES = [
    "AdministratorAccess",
    "PowerUserAccess",
    "IAMFullAccess",
]

# Production indicators in resource names/tags
PRODUCTION_INDICATORS = [
    "prod",
    "production",
    "prd",
    "live",
]


class ResourceMapper:
    """Maps IAM policy statements to Resource and IdentityAccess records."""

    def __init__(self):
        self.resources_created = 0
        self.access_records_created = 0
        self.errors: list[str] = []

    async def map_all_identities(self) -> dict:
        """Process all AWS identities and map their resource access.

        Returns summary with counts.
        """
        self.resources_created = 0
        self.access_records_created = 0
        self.errors = []

        async with async_session_factory() as session:
            stmt = select(Identity).where(
                Identity.type == "AWS_IAM_Role",
                Identity.is_resolved == True,
            )
            result = await session.execute(stmt)
            identities = result.scalars().all()

            logger.info(f"Mapping resource access for {len(identities)} AWS IAM roles")

            for identity in identities:
                try:
                    await self._map_identity_access(session, identity)
                except Exception as e:
                    error_msg = f"Error mapping access for {identity.arn}: {e}"
                    logger.warning(error_msg)
                    self.errors.append(error_msg)

            await session.commit()

        return {
            "resources_created": self.resources_created,
            "access_records_created": self.access_records_created,
            "errors": self.errors,
        }

    async def _map_identity_access(self, session, identity: Identity):
        """Extract resource access from all policies attached to an identity."""
        metadata = identity.metadata_ or {}

        # Collect all policy documents
        policy_documents: list[dict] = []

        # Inline policies
        for policy in metadata.get("inline_policies", []):
            doc = policy.get("document")
            if doc:
                policy_documents.append({"name": policy["name"], "document": doc})

        # Attached managed policies
        for policy in metadata.get("attached_policies", []):
            doc = policy.get("document")
            if doc:
                policy_documents.append({"name": policy["name"], "document": doc})

        # Check for well-known admin policies
        has_admin_policy = any(
            policy.get("name") in ADMIN_POLICY_NAMES
            for policy in metadata.get("attached_policies", [])
        )

        for policy_data in policy_documents:
            document = policy_data["document"]
            if isinstance(document, str):
                import json
                try:
                    document = json.loads(document)
                except Exception:
                    continue

            statements = document.get("Statement", [])
            if isinstance(statements, dict):
                statements = [statements]

            for statement in statements:
                if statement.get("Effect") != "Allow":
                    continue

                actions = statement.get("Action", [])
                resources = statement.get("Resource", [])

                if isinstance(actions, str):
                    actions = [actions]
                if isinstance(resources, str):
                    resources = [resources]

                access_type = self._classify_access_type(actions, has_admin_policy)

                for resource_arn in resources:
                    await self._create_resource_access(
                        session, identity, resource_arn, access_type, actions
                    )

    async def _create_resource_access(
        self,
        session,
        identity: Identity,
        resource_arn: str,
        access_type: str,
        actions: list[str],
    ):
        """Create Resource and IdentityAccess records for a resource ARN."""
        # Determine resource type and name
        if resource_arn == "*":
            resource_type = "Wildcard"
            resource_name = "*"
            classification = "unclassified"
        else:
            resource_type = self._determine_resource_type(resource_arn)
            resource_name = self._extract_resource_name(resource_arn)
            classification = self._determine_classification(resource_arn, resource_name)

        # Find or create resource
        resource = await self._find_or_create_resource(
            session, resource_name, resource_arn, resource_type, classification
        )

        # Create access record
        await self._find_or_create_access(
            session, identity.id, resource.id, access_type, actions
        )

    async def _find_or_create_resource(
        self,
        session,
        name: str,
        arn: str,
        resource_type: str,
        classification: str,
    ) -> Resource:
        """Find existing resource by ARN or create new one."""
        if arn != "*":
            stmt = select(Resource).where(Resource.arn == arn)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                # Update classification if now determined to be production
                if classification == "production" and existing.classification != "production":
                    existing.classification = classification
                return existing

        # For wildcards, look up by name and type
        if arn == "*":
            stmt = select(Resource).where(
                Resource.name == name,
                Resource.resource_type == resource_type,
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                return existing

        new_resource = Resource(
            name=name,
            arn=arn if arn != "*" else None,
            resource_type=resource_type,
            classification=classification,
        )
        session.add(new_resource)
        await session.flush()
        self.resources_created += 1
        return new_resource

    async def _find_or_create_access(
        self,
        session,
        identity_id: uuid.UUID,
        resource_id: uuid.UUID,
        access_type: str,
        actions: list[str],
    ):
        """Find existing access record or create new one."""
        stmt = select(IdentityAccess).where(
            IdentityAccess.identity_id == identity_id,
            IdentityAccess.resource_id == resource_id,
            IdentityAccess.access_type == access_type,
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update actions list
            existing.actions = list(set(existing.actions + actions))
            return existing

        new_access = IdentityAccess(
            identity_id=identity_id,
            resource_id=resource_id,
            access_type=access_type,
            actions=actions[:50],  # Cap stored actions at 50 to limit JSONB size
        )
        session.add(new_access)
        await session.flush()
        self.access_records_created += 1
        return new_access

    @staticmethod
    def _classify_access_type(actions: list[str], has_admin_policy: bool = False) -> str:
        """Classify a set of IAM actions as Read, Write, or Admin."""
        if has_admin_policy:
            return "Admin"

        # Check for admin patterns first
        for action in actions:
            if action == "*" or action == "*:*":
                return "Admin"
            for pattern in ADMIN_ACTION_PATTERNS:
                if re.match(pattern, action, re.IGNORECASE):
                    return "Admin"

        # Check if all actions are read-only
        all_read = True
        for action in actions:
            is_read = False
            for pattern in READ_ACTION_PATTERNS:
                if re.match(pattern, action, re.IGNORECASE):
                    is_read = True
                    break
            if not is_read:
                all_read = False
                break

        if all_read and actions:
            return "Read"

        # Default to Write for any mutating actions
        return "Write"

    @staticmethod
    def _determine_resource_type(arn: str) -> str:
        """Determine resource type from ARN service namespace."""
        # ARN format: arn:partition:service:region:account:resource
        parts = arn.split(":")
        if len(parts) >= 3:
            service = parts[2]
            return SERVICE_RESOURCE_TYPE_MAP.get(service, f"{service.capitalize()}_Resource")
        return "Unknown_Resource"

    @staticmethod
    def _extract_resource_name(arn: str) -> str:
        """Extract a human-readable resource name from an ARN."""
        # Handle partial wildcards (e.g., arn:aws:s3:::my-bucket/*)
        clean_arn = arn.rstrip("/*").rstrip("*")

        # Try to get the last meaningful segment
        if "/" in clean_arn:
            name = clean_arn.split("/")[-1]
        elif ":" in clean_arn:
            name = clean_arn.split(":")[-1]
        else:
            name = clean_arn

        return name if name else arn

    @staticmethod
    def _determine_classification(arn: str, name: str) -> str:
        """Determine if a resource is production-classified."""
        combined = f"{arn} {name}".lower()
        for indicator in PRODUCTION_INDICATORS:
            if indicator in combined:
                return "production"
        return "unclassified"
