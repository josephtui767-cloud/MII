"""AWS Collector — discovers IAM roles, policies, and trust relationships from AWS accounts."""

import asyncio
import logging
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from app.config import settings
from app.database import async_session_factory
from app.models import Identity

logger = logging.getLogger(__name__)

# Throttle retry settings
MAX_RETRIES = 3
BASE_DELAY = 1.0


class AWSCollectorError(Exception):
    """Base exception for AWS collector errors."""
    pass


class AWSAuthError(AWSCollectorError):
    """Authentication/authorization failure."""
    pass


class AWSCollector:
    """Collects IAM role data from AWS accounts."""

    def __init__(self):
        self.discovered_identities: list[dict] = []
        self.errors: list[str] = []

    async def collect_all(self) -> dict:
        """Run discovery across all configured AWS accounts.

        Returns summary dict with counts and errors.
        """
        # Determine accounts to scan
        if settings.use_aws_organizations:
            account_ids = await self._list_org_accounts()
            if not account_ids:
                return {"identities": 0, "errors": ["Failed to list AWS Organizations accounts"]}
            logger.info(f"AWS Organizations: discovered {len(account_ids)} accounts")
        else:
            account_ids = settings.aws_account_ids_list

        if not account_ids:
            logger.warning("No AWS account IDs configured. Skipping AWS collection.")
            return {"identities": 0, "errors": ["No AWS account IDs configured. Set AWS_ACCOUNT_IDS or use 'auto' for Organizations."]}

        self.discovered_identities = []
        self.errors = []

        for account_id in account_ids:
            try:
                await self._collect_account(account_id)
            except AWSAuthError as e:
                error_msg = f"Auth error for account {account_id}: {e}"
                logger.error(error_msg)
                self.errors.append(error_msg)
                # Stop collection for this account per requirement
                continue
            except Exception as e:
                error_msg = f"Unexpected error for account {account_id}: {e}"
                logger.error(error_msg)
                self.errors.append(error_msg)

        # Persist discovered identities
        persisted = await self._persist_identities()

        return {
            "identities": persisted,
            "errors": self.errors,
        }

    async def _list_org_accounts(self) -> list[str]:
        """List all active accounts from AWS Organizations."""
        loop = asyncio.get_event_loop()

        def _fetch_accounts():
            try:
                if settings.AWS_ORG_ROLE_ARN:
                    # Assume org management role
                    sts = boto3.client("sts", region_name=settings.AWS_REGION)
                    creds = sts.assume_role(
                        RoleArn=settings.AWS_ORG_ROLE_ARN,
                        RoleSessionName="MII-OrgDiscovery",
                    )["Credentials"]
                    org_client = boto3.client(
                        "organizations",
                        aws_access_key_id=creds["AccessKeyId"],
                        aws_secret_access_key=creds["SecretAccessKey"],
                        aws_session_token=creds["SessionToken"],
                    )
                else:
                    org_client = boto3.client("organizations", region_name=settings.AWS_REGION)

                accounts = []
                paginator = org_client.get_paginator("list_accounts")
                for page in paginator.paginate():
                    for account in page["Accounts"]:
                        if account["Status"] == "ACTIVE":
                            accounts.append(account["Id"])
                return accounts
            except ClientError as e:
                logger.error(f"Failed to list Organizations accounts: {e}")
                self.errors.append(f"AWS Organizations error: {e}")
                return []
            except Exception as e:
                logger.error(f"Unexpected error listing Organizations accounts: {e}")
                self.errors.append(f"AWS Organizations error: {e}")
                return []

        return await loop.run_in_executor(None, _fetch_accounts)

    async def _collect_account(self, account_id: str):
        """Collect all IAM roles from a single AWS account."""
        logger.info(f"Starting AWS collection for account {account_id}")

        iam_client = await self._get_iam_client(account_id)
        roles = await self._list_all_roles(iam_client, account_id)

        logger.info(f"Found {len(roles)} roles in account {account_id}")

        for role in roles:
            try:
                identity_data = await self._process_role(iam_client, role, account_id)
                self.discovered_identities.append(identity_data)
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code in ("AccessDenied", "UnauthorizedAccess"):
                    raise AWSAuthError(f"Access denied processing role {role['RoleName']}: {e}")
                # Per-role error: log and continue
                error_msg = f"Error processing role {role['Arn']}: {e}"
                logger.warning(error_msg)
                self.errors.append(error_msg)
            except Exception as e:
                error_msg = f"Error processing role {role.get('Arn', 'unknown')}: {e}"
                logger.warning(error_msg)
                self.errors.append(error_msg)

    async def _get_iam_client(self, account_id: str):
        """Get boto3 IAM client, optionally assuming a role for cross-account access."""
        loop = asyncio.get_event_loop()

        def _create_client():
            if settings.AWS_ASSUME_ROLE_ARN:
                # Assume role in target account
                sts = boto3.client("sts", region_name=settings.AWS_REGION)
                role_arn = settings.AWS_ASSUME_ROLE_ARN.replace(
                    settings.AWS_ASSUME_ROLE_ARN.split(":")[4], account_id
                )
                credentials = sts.assume_role(
                    RoleArn=role_arn,
                    RoleSessionName="MII-Discovery",
                )["Credentials"]
                return boto3.client(
                    "iam",
                    region_name=settings.AWS_REGION,
                    aws_access_key_id=credentials["AccessKeyId"],
                    aws_secret_access_key=credentials["SecretAccessKey"],
                    aws_session_token=credentials["SessionToken"],
                )
            else:
                return boto3.client("iam", region_name=settings.AWS_REGION)

        return await loop.run_in_executor(None, _create_client)

    async def _list_all_roles(self, iam_client, account_id: str) -> list[dict]:
        """Paginate through all IAM roles with throttle retry."""
        loop = asyncio.get_event_loop()
        roles: list[dict] = []

        def _paginate():
            paginator = iam_client.get_paginator("list_roles")
            all_roles = []
            for page in paginator.paginate():
                all_roles.extend(page["Roles"])
            return all_roles

        for attempt in range(MAX_RETRIES + 1):
            try:
                roles = await loop.run_in_executor(None, _paginate)
                break
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code in ("AccessDenied", "UnauthorizedAccess", "InvalidClientTokenId"):
                    raise AWSAuthError(f"Authentication failed for account {account_id}: {e}")
                if error_code == "Throttling" and attempt < MAX_RETRIES:
                    delay = BASE_DELAY * (2 ** attempt)
                    logger.warning(f"Throttled listing roles for {account_id}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                raise

        return roles

    async def _process_role(self, iam_client, role: dict, account_id: str) -> dict:
        """Extract full role data including policies and trust policy."""
        role_name = role["RoleName"]
        role_arn = role["Arn"]

        # Extract trust policy (already in role response)
        trust_policy = role.get("AssumeRolePolicyDocument", {})

        # Get inline policies
        inline_policies = await self._get_inline_policies(iam_client, role_name)

        # Get attached managed policies
        attached_policies = await self._get_attached_policies(iam_client, role_name)

        # Get last used info
        last_used = await self._get_role_last_used(iam_client, role_name)

        return {
            "name": role_name,
            "arn": role_arn,
            "type": "AWS_IAM_Role",
            "source": "AWS",
            "account_id": account_id,
            "last_used_at": last_used,
            "metadata": {
                "trust_policy": trust_policy,
                "inline_policies": inline_policies,
                "attached_policies": attached_policies,
                "creation_date": role.get("CreateDate", "").isoformat() if role.get("CreateDate") else None,
                "path": role.get("Path", "/"),
                "description": role.get("Description", ""),
            },
        }

    async def _get_inline_policies(self, iam_client, role_name: str) -> list[dict]:
        """Get all inline policy documents for a role."""
        loop = asyncio.get_event_loop()

        def _fetch():
            policies = []
            try:
                paginator = iam_client.get_paginator("list_role_policies")
                for page in paginator.paginate(RoleName=role_name):
                    for policy_name in page["PolicyNames"]:
                        policy_doc = iam_client.get_role_policy(
                            RoleName=role_name, PolicyName=policy_name
                        )
                        policies.append({
                            "name": policy_name,
                            "document": policy_doc["PolicyDocument"],
                        })
            except ClientError as e:
                if e.response["Error"]["Code"] == "Throttling":
                    raise
                logger.warning(f"Could not get inline policies for {role_name}: {e}")
            return policies

        for attempt in range(MAX_RETRIES + 1):
            try:
                return await loop.run_in_executor(None, _fetch)
            except ClientError as e:
                if e.response["Error"]["Code"] == "Throttling" and attempt < MAX_RETRIES:
                    await asyncio.sleep(BASE_DELAY * (2 ** attempt))
                    continue
                raise

        return []

    async def _get_attached_policies(self, iam_client, role_name: str) -> list[dict]:
        """Get all attached managed policies for a role."""
        loop = asyncio.get_event_loop()

        def _fetch():
            policies = []
            try:
                paginator = iam_client.get_paginator("list_attached_role_policies")
                for page in paginator.paginate(RoleName=role_name):
                    for policy in page["AttachedPolicies"]:
                        # Get the actual policy document
                        policy_detail = iam_client.get_policy(PolicyArn=policy["PolicyArn"])
                        version_id = policy_detail["Policy"]["DefaultVersionId"]
                        policy_version = iam_client.get_policy_version(
                            PolicyArn=policy["PolicyArn"], VersionId=version_id
                        )
                        policies.append({
                            "name": policy["PolicyName"],
                            "arn": policy["PolicyArn"],
                            "document": policy_version["PolicyVersion"]["Document"],
                        })
            except ClientError as e:
                if e.response["Error"]["Code"] == "Throttling":
                    raise
                logger.warning(f"Could not get attached policies for {role_name}: {e}")
            return policies

        for attempt in range(MAX_RETRIES + 1):
            try:
                return await loop.run_in_executor(None, _fetch)
            except ClientError as e:
                if e.response["Error"]["Code"] == "Throttling" and attempt < MAX_RETRIES:
                    await asyncio.sleep(BASE_DELAY * (2 ** attempt))
                    continue
                raise

        return []

    async def _get_role_last_used(self, iam_client, role_name: str) -> datetime | None:
        """Get when a role was last used."""
        loop = asyncio.get_event_loop()

        def _fetch():
            try:
                response = iam_client.get_role(RoleName=role_name)
                last_used_info = response["Role"].get("RoleLastUsed", {})
                return last_used_info.get("LastUsedDate")
            except ClientError:
                return None

        return await loop.run_in_executor(None, _fetch)

    async def _persist_identities(self) -> int:
        """Store discovered identities in PostgreSQL."""
        if not self.discovered_identities:
            return 0

        persisted = 0
        async with async_session_factory() as session:
            for identity_data in self.discovered_identities:
                try:
                    # Upsert by ARN
                    from sqlalchemy import select
                    stmt = select(Identity).where(Identity.arn == identity_data["arn"])
                    result = await session.execute(stmt)
                    existing = result.scalar_one_or_none()

                    if existing:
                        existing.name = identity_data["name"]
                        existing.account_id = identity_data["account_id"]
                        existing.last_used_at = identity_data["last_used_at"]
                        existing.metadata_ = identity_data["metadata"]
                        existing.is_resolved = True
                    else:
                        new_identity = Identity(
                            name=identity_data["name"],
                            arn=identity_data["arn"],
                            type=identity_data["type"],
                            source=identity_data["source"],
                            account_id=identity_data["account_id"],
                            last_used_at=identity_data["last_used_at"],
                            metadata_=identity_data["metadata"],
                            is_resolved=True,
                        )
                        session.add(new_identity)

                    persisted += 1
                except Exception as e:
                    logger.error(f"Failed to persist identity {identity_data.get('arn')}: {e}")
                    self.errors.append(f"Persist error: {identity_data.get('arn')}: {e}")

            await session.commit()

        logger.info(f"Persisted {persisted} AWS identities")
        return persisted
