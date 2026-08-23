"""
Amazon AI Fulfillment Assistant - FastAPI Backend

Chunk 1B: Backend Foundation
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import logger, setup_logging

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
setup_logging()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Starting %s v%s (%s)", settings.APP_NAME, settings.APP_VERSION, settings.APP_ENV)
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered order fulfillment workspace for Amazon sellers",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — localhost development origins only
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
register_error_handlers(app)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
def health_check():
    """Root health check endpoint."""
    return {"status": "ok"}


# Mount API v1 routes
app.include_router(api_v1_router)
