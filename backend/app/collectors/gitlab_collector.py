"""GitLab Collector — discovers CI/CD identities, access tokens, and OIDC configs from GitLab."""

import asyncio
import logging

import gitlab
from gitlab.exceptions import GitlabAuthenticationError

from app.config import settings
from app.database import async_session_factory
from app.models import Identity
from sqlalchemy import select

logger = logging.getLogger(__name__)


class GitLabCollectorError(Exception):
    """Base exception for GitLab collector errors."""
    pass


class GitLabAuthError(GitLabCollectorError):
    """Authentication failure — stops all collection."""
    pass


class GitLabCollector:
    """Collects identity data from GitLab SaaS (groups, projects, tokens, OIDC)."""

    def __init__(self):
        self.discovered_identities: list[dict] = []
        self.errors: list[str] = []
        self._gl: gitlab.Gitlab | None = None

    async def collect_all(self) -> dict:
        """Run full GitLab discovery.

        Returns summary dict with counts and errors.
        """
        if not settings.GITLAB_TOKEN:
            logger.warning("No GitLab token configured. Skipping GitLab collection.")
            return {"identities": 0, "errors": ["No GitLab token configured"]}

        self.discovered_identities = []
        self.errors = []

        try:
            await asyncio.wait_for(self._authenticate(), timeout=30)
        except asyncio.TimeoutError:
            return {"identities": 0, "errors": ["GitLab authentication timed out"]}
        except GitLabAuthError as e:
            return {"identities": 0, "errors": [str(e)]}

        # Collect groups and their tokens (with timeout)
        try:
            await asyncio.wait_for(self._collect_groups(), timeout=120)
        except asyncio.TimeoutError:
            self.errors.append("GitLab group collection timed out")

        # Collect projects and their tokens/OIDC configs (with timeout)
        try:
            await asyncio.wait_for(self._collect_projects(), timeout=120)
        except asyncio.TimeoutError:
            self.errors.append("GitLab project collection timed out")

        # Persist
        persisted = await self._persist_identities()

        return {
            "identities": persisted,
            "errors": self.errors,
        }

    async def _authenticate(self):
        """Initialize GitLab client and verify authentication."""
        loop = asyncio.get_event_loop()

        def _init():
            gl = gitlab.Gitlab(
                url=settings.GITLAB_URL,
                private_token=settings.GITLAB_TOKEN,
            )
            gl.auth()
            return gl

        try:
            self._gl = await loop.run_in_executor(None, _init)
            logger.info(f"Authenticated to GitLab at {settings.GITLAB_URL}")
        except GitlabAuthenticationError as e:
            raise GitLabAuthError(f"GitLab authentication failed for {settings.GITLAB_URL}: {e}")
        except Exception as e:
            raise GitLabAuthError(f"GitLab connection failed for {settings.GITLAB_URL}: {e}")

    async def _collect_groups(self):
        """Retrieve all accessible groups and their access tokens."""
        loop = asyncio.get_event_loop()
        logger.info("Collecting GitLab groups...")

        def _list_groups():
            return list(self._gl.groups.list(iterator=True, per_page=100))

        try:
            groups = await loop.run_in_executor(None, _list_groups)
        except Exception as e:
            error_msg = f"Failed to list groups: {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return

        logger.info(f"Found {len(groups)} groups")

        for group in groups:
            await self._collect_group_tokens(group)

    async def _collect_group_tokens(self, group):
        """Extract group access tokens for a group."""
        loop = asyncio.get_event_loop()

        def _get_tokens():
            try:
                # python-gitlab uses group.access_tokens for group access tokens
                tokens = list(group.access_tokens.list(iterator=True))
                return tokens
            except gitlab.exceptions.GitlabListError as e:
                if e.response_code == 403:
                    raise PermissionError(f"403 for group {group.full_path}")
                if e.response_code == 429:
                    raise RateLimitError(e)
                raise
            except Exception:
                return []

        try:
            tokens = await loop.run_in_executor(None, _get_tokens)
            for token in tokens:
                self.discovered_identities.append({
                    "name": f"{group.full_path}/{token.name}",
                    "arn": f"gitlab:group_token:{group.id}:{token.id}",
                    "type": "GitLab_Group_Access_Token",
                    "source": "GitLab",
                    "owner": group.full_path,
                    "last_used_at": None,  # GitLab doesn't expose last-used for tokens easily
                    "metadata": {
                        "group_id": group.id,
                        "group_path": group.full_path,
                        "token_name": token.name,
                        "scopes": getattr(token, "scopes", []),
                        "expires_at": getattr(token, "expires_at", None),
                        "active": getattr(token, "active", True),
                        "revoked": getattr(token, "revoked", False),
                    },
                })
        except PermissionError as e:
            error_msg = f"Permission denied for group tokens: {group.full_path}"
            logger.warning(error_msg)
            self.errors.append(error_msg)
        except Exception as e:
            if _is_rate_limit(e):
                await self._handle_rate_limit(e)
                # Retry once after rate limit
                try:
                    tokens = await loop.run_in_executor(None, _get_tokens)
                    for token in tokens:
                        self.discovered_identities.append({
                            "name": f"{group.full_path}/{token.name}",
                            "arn": f"gitlab:group_token:{group.id}:{token.id}",
                            "type": "GitLab_Group_Access_Token",
                            "source": "GitLab",
                            "owner": group.full_path,
                            "last_used_at": None,
                            "metadata": {
                                "group_id": group.id,
                                "group_path": group.full_path,
                                "token_name": token.name,
                                "scopes": getattr(token, "scopes", []),
                                "expires_at": getattr(token, "expires_at", None),
                                "active": getattr(token, "active", True),
                                "revoked": getattr(token, "revoked", False),
                            },
                        })
                except Exception:
                    pass
            else:
                error_msg = f"Error collecting group tokens for {group.full_path}: {e}"
                logger.warning(error_msg)
                self.errors.append(error_msg)

    async def _collect_projects(self):
        """Retrieve all accessible projects and their tokens/OIDC configs."""
        loop = asyncio.get_event_loop()
        logger.info("Collecting GitLab projects...")

        def _list_projects():
            return list(self._gl.projects.list(iterator=True, per_page=100))

        try:
            projects = await loop.run_in_executor(None, _list_projects)
        except Exception as e:
            error_msg = f"Failed to list projects: {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return

        logger.info(f"Found {len(projects)} projects")

        for project in projects:
            await self._collect_project_tokens(project)
            await self._collect_project_ci_variables(project)
            await self._collect_project_oidc(project)

    async def _collect_project_tokens(self, project):
        """Extract project access tokens."""
        loop = asyncio.get_event_loop()

        def _get_tokens():
            try:
                tokens = list(project.access_tokens.list(iterator=True))
                return tokens
            except gitlab.exceptions.GitlabListError as e:
                if e.response_code == 403:
                    raise PermissionError(f"403 for project {project.path_with_namespace}")
                raise
            except Exception:
                return []

        try:
            tokens = await loop.run_in_executor(None, _get_tokens)
            for token in tokens:
                self.discovered_identities.append({
                    "name": f"{project.path_with_namespace}/{token.name}",
                    "arn": f"gitlab:project_token:{project.id}:{token.id}",
                    "type": "GitLab_Project_Access_Token",
                    "source": "GitLab",
                    "owner": project.path_with_namespace,
                    "last_used_at": None,
                    "metadata": {
                        "project_id": project.id,
                        "project_path": project.path_with_namespace,
                        "token_name": token.name,
                        "scopes": getattr(token, "scopes", []),
                        "expires_at": getattr(token, "expires_at", None),
                        "active": getattr(token, "active", True),
                        "revoked": getattr(token, "revoked", False),
                    },
                })
        except PermissionError:
            error_msg = f"Permission denied for project tokens: {project.path_with_namespace}"
            logger.warning(error_msg)
            self.errors.append(error_msg)
        except Exception as e:
            if _is_rate_limit(e):
                await self._handle_rate_limit(e)
            else:
                error_msg = f"Error collecting project tokens for {project.path_with_namespace}: {e}"
                logger.warning(error_msg)
                self.errors.append(error_msg)

    async def _collect_project_ci_variables(self, project):
        """Extract CI/CD variable configurations (keys only, NOT values)."""
        loop = asyncio.get_event_loop()

        def _get_variables():
            try:
                variables = list(project.variables.list(iterator=True))
                return [
                    {
                        "key": var.key,
                        "protected": var.protected,
                        "masked": var.masked,
                        "environment_scope": getattr(var, "environment_scope", "*"),
                    }
                    for var in variables
                ]
            except gitlab.exceptions.GitlabListError as e:
                if e.response_code in (403, 404):
                    return []
                raise
            except Exception:
                return []

        try:
            variables = await loop.run_in_executor(None, _get_variables)
            # Store CI variables as metadata on the project — not as separate identities
            # They'll be referenced during trust relationship mapping
            if variables:
                # Find or update project identity metadata
                for identity in self.discovered_identities:
                    if identity.get("metadata", {}).get("project_id") == project.id:
                        identity["metadata"]["ci_variables"] = variables
                        break
        except Exception as e:
            if _is_rate_limit(e):
                await self._handle_rate_limit(e)

    async def _collect_project_oidc(self, project):
        """Extract OIDC integration configuration for the project."""
        loop = asyncio.get_event_loop()

        def _get_oidc():
            try:
                # Check .gitlab-ci.yml or project CI/CD settings for OIDC
                # GitLab OIDC is configured via id_tokens in .gitlab-ci.yml
                # We check project-level CI/CD settings for OIDC audience
                ci_config = {}

                # Try to get the CI/CD config file reference
                try:
                    ci_file = project.files.get(file_path=".gitlab-ci.yml", ref="main")
                    # We do NOT read source code content per requirement
                    # We only note that OIDC configuration exists
                    ci_config["has_ci_config"] = True
                except Exception:
                    ci_config["has_ci_config"] = False

                return ci_config
            except Exception:
                return {}

        try:
            oidc_config = await loop.run_in_executor(None, _get_oidc)
            # Store OIDC presence as metadata — actual OIDC relationships
            # are determined from AWS trust policies referencing GitLab OIDC provider
            if oidc_config.get("has_ci_config"):
                for identity in self.discovered_identities:
                    if identity.get("metadata", {}).get("project_id") == project.id:
                        identity["metadata"]["has_ci_config"] = True
                        break
        except Exception:
            pass  # Non-critical, continue

    async def _handle_rate_limit(self, error):
        """Handle GitLab 429 rate limit by waiting per Retry-After header."""
        retry_after = 60  # Default wait if no header
        if hasattr(error, "response_headers"):
            retry_after = int(error.response_headers.get("Retry-After", 60))
        elif hasattr(error, "retry_after"):
            retry_after = int(error.retry_after)

        logger.warning(f"GitLab rate limited. Waiting {retry_after}s...")
        await asyncio.sleep(retry_after)

    async def _persist_identities(self) -> int:
        """Store discovered GitLab identities in PostgreSQL."""
        if not self.discovered_identities:
            return 0

        persisted = 0
        async with async_session_factory() as session:
            for identity_data in self.discovered_identities:
                try:
                    stmt = select(Identity).where(Identity.arn == identity_data["arn"])
                    result = await session.execute(stmt)
                    existing = result.scalar_one_or_none()

                    if existing:
                        existing.name = identity_data["name"]
                        existing.owner = identity_data.get("owner")
                        existing.last_used_at = identity_data.get("last_used_at")
                        existing.metadata_ = identity_data["metadata"]
                        existing.is_resolved = True
                    else:
                        new_identity = Identity(
                            name=identity_data["name"],
                            arn=identity_data["arn"],
                            type=identity_data["type"],
                            source=identity_data["source"],
                            owner=identity_data.get("owner"),
                            last_used_at=identity_data.get("last_used_at"),
                            metadata_=identity_data["metadata"],
                            is_resolved=True,
                        )
                        session.add(new_identity)

                    persisted += 1
                except Exception as e:
                    logger.error(f"Failed to persist GitLab identity {identity_data.get('arn')}: {e}")
                    self.errors.append(f"Persist error: {identity_data.get('arn')}: {e}")

            await session.commit()

        logger.info(f"Persisted {persisted} GitLab identities")
        return persisted


def _is_rate_limit(error) -> bool:
    """Check if an error is a rate limit (429) response."""
    if hasattr(error, "response_code") and error.response_code == 429:
        return True
    if hasattr(error, "status_code") and error.status_code == 429:
        return True
    return False


class RateLimitError(Exception):
    """Wrapper for rate limit errors."""
    def __init__(self, original):
        self.original = original
        self.response_headers = getattr(original, "response_headers", {})
