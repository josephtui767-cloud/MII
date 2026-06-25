"""Discovery API endpoints — trigger and monitor discovery scans."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks

from app.collectors.aws_collector import AWSCollector
from app.collectors.gitlab_collector import GitLabCollector
from app.schemas.discovery import DiscoveryRunResponse, DiscoveryStatusResponse
from app.services.graph_engine import graph_engine
from app.services.resource_mapper import ResourceMapper
from app.services.risk_engine import RiskEngine
from app.services.trust_parser import TrustParser

router = APIRouter()
logger = logging.getLogger(__name__)

# Discovery state (in-memory for simplicity; could be persisted)
_discovery_state = {
    "status": "idle",
    "last_run_at": None,
    "last_duration_seconds": None,
    "identities_discovered": 0,
    "trust_relationships_discovered": 0,
    "resources_discovered": 0,
    "errors": [],
}


async def _run_discovery():
    """Background task: run full discovery pipeline."""
    global _discovery_state
    _discovery_state["status"] = "running"
    _discovery_state["errors"] = []
    start_time = datetime.now(timezone.utc)

    total_identities = 0
    total_relationships = 0
    total_resources = 0
    all_errors: list[str] = []

    try:
        # Step 1: AWS Collection
        logger.info("Discovery Step 1/5: AWS Collection")
        aws_collector = AWSCollector()
        aws_result = await aws_collector.collect_all()
        total_identities += aws_result.get("identities", 0)
        all_errors.extend(aws_result.get("errors", []))

        # Step 2: GitLab Collection
        logger.info("Discovery Step 2/5: GitLab Collection")
        gitlab_collector = GitLabCollector()
        gitlab_result = await gitlab_collector.collect_all()
        total_identities += gitlab_result.get("identities", 0)
        all_errors.extend(gitlab_result.get("errors", []))

        # Step 3: Trust Relationship Parsing
        logger.info("Discovery Step 3/5: Trust Relationship Parsing")
        trust_parser = TrustParser()
        trust_result = await trust_parser.parse_all_identities()
        total_relationships += trust_result.get("relationships_created", 0)
        all_errors.extend(trust_result.get("errors", []))

        # Step 4: Resource Access Mapping
        logger.info("Discovery Step 4/5: Resource Access Mapping")
        resource_mapper = ResourceMapper()
        resource_result = await resource_mapper.map_all_identities()
        total_resources += resource_result.get("resources_created", 0)
        all_errors.extend(resource_result.get("errors", []))

        # Step 5: Risk Score Recalculation
        logger.info("Discovery Step 5/5: Risk Score Recalculation")
        risk_engine = RiskEngine()
        risk_result = await risk_engine.recalculate_all()
        all_errors.extend(risk_result.get("errors", []))

        # Rebuild graph
        logger.info("Rebuilding trust graph...")
        await graph_engine.rebuild()

        _discovery_state["status"] = "completed"
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        _discovery_state["status"] = "failed"
        all_errors.append(f"Discovery pipeline error: {e}")

    end_time = datetime.now(timezone.utc)
    _discovery_state["last_run_at"] = end_time
    _discovery_state["last_duration_seconds"] = (end_time - start_time).total_seconds()
    _discovery_state["identities_discovered"] = total_identities
    _discovery_state["trust_relationships_discovered"] = total_relationships
    _discovery_state["resources_discovered"] = total_resources
    _discovery_state["errors"] = all_errors[:50]  # Cap stored errors

    logger.info(
        f"Discovery complete: {total_identities} identities, "
        f"{total_relationships} relationships, {total_resources} resources, "
        f"{len(all_errors)} errors"
    )


@router.post("/discovery/run", response_model=DiscoveryRunResponse)
async def run_discovery(background_tasks: BackgroundTasks):
    """Trigger a full discovery scan (runs in background)."""
    if _discovery_state["status"] == "running":
        return DiscoveryRunResponse(
            status="already_running",
            message="A discovery scan is already in progress.",
            started_at=_discovery_state.get("last_run_at"),
        )

    background_tasks.add_task(_run_discovery)

    return DiscoveryRunResponse(
        status="started",
        message="Discovery scan started. Check /discovery/status for progress.",
        started_at=datetime.now(timezone.utc),
    )


@router.get("/discovery/status", response_model=DiscoveryStatusResponse)
async def get_discovery_status():
    """Get the status of the current or last discovery scan."""
    return DiscoveryStatusResponse(
        status=_discovery_state["status"],
        last_run_at=_discovery_state["last_run_at"],
        last_duration_seconds=_discovery_state["last_duration_seconds"],
        identities_discovered=_discovery_state["identities_discovered"],
        trust_relationships_discovered=_discovery_state["trust_relationships_discovered"],
        resources_discovered=_discovery_state["resources_discovered"],
        errors=_discovery_state["errors"],
    )
