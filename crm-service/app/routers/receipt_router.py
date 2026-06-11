"""
Receipt API Router — Handles delivery event callbacks from the channel service.

This is the idempotent callback endpoint — the system design centerpiece.

Endpoint:
  POST /api/receipts    — Process delivery event (sent/delivered/opened/clicked/failed)

Design:
  1. Insert event into delivery_events with UNIQUE(idempotency_key)
     → Duplicate? Return 200 "duplicate" (not 409, channel service treats both as success)
  2. Update communication status (forward-only enforcement)
  3. Increment campaign counter (denormalized for fast reads)
"""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.database import get_main_pool
from app.models.campaign import DeliveryReceiptRequest, DeliveryReceiptResponse
from app.repositories import campaign_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/receipts", tags=["Receipts"])


@router.post(
    "",
    response_model=DeliveryReceiptResponse,
    status_code=202,
    summary="Process delivery receipt",
    description=(
        "Idempotent callback endpoint for the channel service. "
        "Incoming receipts are queued in Redis and processed asynchronously. "
        "Duplicate events are safely ignored at write time. "
        "Status transitions are forward-only (sent→delivered→opened→clicked→converted)."
    ),
)
async def process_receipt(receipt: DeliveryReceiptRequest):
    """
    Process a delivery event callback.

    Decoupled via Redis queue:
    Pushes callback details to `crm_receipt_queue` and returns immediately.
    A background worker pops events and batch-updates the DB.
    """
    try:
        UUID(receipt.communication_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid communication_id format")

    # Push to Redis receipt queue
    from app.services.redis_queue import push_to_queue
    payload = receipt.dict()
    push_to_queue("crm_receipt_queue", payload)

    return DeliveryReceiptResponse(status="queued")
