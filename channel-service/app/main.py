"""
Xeno Channel Service — Stub Delivery Simulator.

This service simulates the behavior of real messaging channels
(WhatsApp, SMS, Email, RCS). It:
  1. Accepts send requests from the CRM service
  2. Simulates async delivery with probabilistic outcomes
  3. Fires callbacks to the CRM receipt API with delivery events

The delivery lifecycle:
  sent → delivered (90%) → opened (60%) → clicked (30%)

Each callback includes an idempotency_key so the CRM can safely
handle duplicates from retries.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.simulator import schedule_delivery, cancel_all_simulations

# ── Configure Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Request/Response Models ──
class Recipient(BaseModel):
    """Contact information for the message recipient."""
    phone: Optional[str] = None
    email: Optional[str] = None
    whatsapp_id: Optional[str] = None


class SendRequest(BaseModel):
    """
    Request to send a message through a channel.

    The CRM service sends this when dispatching campaign messages.
    Each request triggers an independent async delivery simulation.
    """
    communication_id: str = Field(
        ..., description="Unique ID for this communication (from CRM)"
    )
    recipient: Recipient = Field(
        ..., description="Contact info for the recipient"
    )
    message: str = Field(
        ..., description="The personalized message content"
    )
    channel: str = Field(
        ..., description="Channel type: whatsapp, sms, email, rcs"
    )


class SendResponse(BaseModel):
    """Acknowledgement that the send request was accepted."""
    status: str = "queued"
    communication_id: str
    message: str = "Delivery simulation started"


# ── Application Lifespan ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown for the channel service."""
    settings = get_settings()
    logger.info(f"Starting {settings.APP_NAME}...")
    logger.info(f"  CRM callback URL: {settings.CRM_RECEIPT_URL}")
    
    # Start background simulation worker
    import asyncio
    from app.workers.simulation_worker import start_simulation_worker
    app.state.simulation_worker_task = asyncio.create_task(start_simulation_worker(), name="simulation_worker")
    logger.info("✓ Simulation worker started")
    
    logger.info(f"✓ {settings.APP_NAME} ready — accepting send requests")
    yield
    # Graceful shutdown: cancel worker and simulations
    if hasattr(app.state, "simulation_worker_task"):
        app.state.simulation_worker_task.cancel()
    cancelled = await cancel_all_simulations()
    logger.info(f"✓ {settings.APP_NAME} shutdown complete ({cancelled} simulations cancelled)")


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


# ── Send Endpoint ──
@app.post(
    "/api/send",
    response_model=SendResponse,
    status_code=202,
    tags=["Channel"],
    summary="Send a message through a channel",
    description=(
        "Accepts a message for delivery and immediately returns 202 Accepted. "
        "The actual delivery is simulated asynchronously — callbacks will be "
        "fired to the CRM receipt API as the message progresses through the "
        "delivery lifecycle (sent → delivered → opened → clicked)."
    ),
)
async def send_message(request: SendRequest) -> SendResponse:
    """
    Accept a message for delivery simulation.

    Returns 202 immediately — the delivery happens asynchronously.
    The CRM will receive callbacks at its receipt API as delivery
    events occur (sent, delivered, opened, clicked, or failed).
    """
    # Validate channel
    valid_channels = {"whatsapp", "sms", "email", "rcs"}
    if request.channel.lower() not in valid_channels:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid channel '{request.channel}'. Must be one of: {valid_channels}",
        )

    # Push to Redis queue for async processing
    from app.services.redis_queue import push_to_queue
    push_to_queue("channel_simulation_queue", {
        "communication_id": request.communication_id,
        "recipient": request.recipient.model_dump(),
        "message": request.message,
        "channel": request.channel.lower(),
    })

    logger.info(
        f"Accepted send request: comm={request.communication_id[:8]}... "
        f"channel={request.channel}"
    )

    return SendResponse(
        status="queued",
        communication_id=request.communication_id,
        message=f"Delivery simulation started for {request.channel}",
    )
