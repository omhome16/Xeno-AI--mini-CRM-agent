"""
Xeno Channel Service — Stub Delivery Simulator.

This service simulates the behavior of real messaging channels
(WhatsApp, SMS, Email, RCS). It:
  1. Accepts send requests from the CRM service
  2. Simulates async delivery with probabilistic outcomes
  3. Fires callbacks to the CRM receipt API with delivery events

This is a separate deployment to demonstrate microservice architecture
and realistic async webhook patterns.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.config import get_settings

# ── Configure Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Application Lifespan ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown for the channel service."""
    settings = get_settings()
    logger.info(f"Starting {settings.APP_NAME}...")
    logger.info(f"  CRM callback URL: {settings.CRM_RECEIPT_URL}")
    logger.info(f"✓ {settings.APP_NAME} ready")
    yield
    logger.info(f"✓ {settings.APP_NAME} shutdown complete")


# ── Create FastAPI Application ──
settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="Stub channel service that simulates message delivery and fires webhooks",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Health Check ──
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "channel-service",
        "version": "0.1.0",
    }


# ── API Root ──
@app.get("/", tags=["System"])
async def root():
    """API root."""
    return {
        "service": settings.APP_NAME,
        "version": "0.1.0",
        "docs": "/docs",
    }


# ── Send Endpoint ── (Full implementation in Phase 2)
# POST /api/send will be added with the delivery simulator
