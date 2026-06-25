"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown logic."""
    logger.info("Starting Machine Identity Intelligence Platform")
    logger.info(f"Environment: {settings.APP_ENV}")

    # Import here to avoid circular imports at module level
    from app.services.graph_engine import graph_engine

    # Build graph from existing data on startup
    try:
        await graph_engine.rebuild()
        logger.info("Trust graph loaded")
    except Exception as e:
        logger.warning(f"Could not load trust graph on startup: {e}")

    yield

    # Shutdown
    await engine.dispose()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Machine Identity Intelligence",
    description="Discover, inventory, visualize, and risk-score machine identities across GitLab and AWS.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/api/v1/health", tags=["health"])
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "mii-backend", "version": "0.1.0"}


# Register routers
from app.api.identities import router as identities_router  # noqa: E402
from app.api.discovery import router as discovery_router  # noqa: E402
from app.api.graph import router as graph_router  # noqa: E402
from app.api.risk import router as risk_router  # noqa: E402
from app.api.ai import router as ai_router  # noqa: E402
from app.api.security import router as security_router  # noqa: E402
from app.api.reports import router as reports_router  # noqa: E402

app.include_router(identities_router, prefix="/api/v1", tags=["identities"])
app.include_router(discovery_router, prefix="/api/v1", tags=["discovery"])
app.include_router(graph_router, prefix="/api/v1", tags=["graph"])
app.include_router(risk_router, prefix="/api/v1", tags=["risk"])
app.include_router(ai_router, prefix="/api/v1", tags=["ai"])
app.include_router(security_router, prefix="/api/v1", tags=["security"])
app.include_router(reports_router, prefix="/api/v1", tags=["reports"])
