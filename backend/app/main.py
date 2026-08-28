"""
Amazon AI Fulfillment Assistant - FastAPI Backend

v0.2.0: Added authentication, multi-tenancy, and database foundation.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.auth.routes import router as auth_router
from app.auth.organization_routes import router as org_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import logger, setup_logging

# -------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------
setup_logging()


# -------------------------------------------------------------------
# Lifespan
# -------------------------------------------------------------------
@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info(
        "Starting %s v%s (%s)", settings.APP_NAME, settings.APP_VERSION, settings.APP_ENV
    )
    # Note: order_service's temporary synchronous bridge (Phase 2B) no longer
    # needs anything from this lifespan — it runs its own dedicated,
    # process-lifetime event loop, independent of however many times this
    # ASGI lifespan starts/stops (e.g. once per `with TestClient(app):` in
    # tests). See order_service.py's module docstring for why.
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


# -------------------------------------------------------------------
# Application
# -------------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered order fulfillment workspace for Amazon sellers",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# -------------------------------------------------------------------
# CORS
# -------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# Error handlers
# -------------------------------------------------------------------
register_error_handlers(app)

# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------


@app.get("/health")
def health_check():
    """Root health check endpoint."""
    return {"status": "ok"}


# Auth routes (no /api/v1 prefix — matches Digital-FTE convention)
app.include_router(auth_router)

# Organization routes
app.include_router(org_router)

# API v1 routes (existing fulfillment, orders, inventory, etc.)
app.include_router(api_v1_router)
