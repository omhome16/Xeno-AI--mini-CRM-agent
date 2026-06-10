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
    summary="Process delivery receipt",
    description=(
        "Idempotent callback endpoint for the channel service. "
        "Duplicate events (same idempotency_key) are silently accepted. "
        "Status transitions are forward-only (sent→delivered→opened→clicked)."
    ),
)
async def process_receipt(receipt: DeliveryReceiptRequest):
    """
    Process a delivery event callback.

    Flow:
      1. Try to insert into delivery_events (atomic dedup via UNIQUE constraint)
      2. If duplicate → return "duplicate" (success, just already processed)
      3. Update communication status (forward-only, rejects out-of-order)
      4. Increment campaign counter

    This is the idempotent receipt processing described in the blueprint —
    the UNIQUE constraint on idempotency_key means we can never double-count
    events, even with concurrent callbacks or retries.
    """
    pool = get_main_pool()

    try:
        comm_id = UUID(receipt.communication_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid communication_id format")

    # ── Step 1: Insert delivery event (atomic dedup) ──
    is_new = await campaign_repo.insert_delivery_event(
        pool=pool,
        communication_id=comm_id,
        event_type=receipt.event_type,
        event_data=receipt.event_data,
        idempotency_key=receipt.idempotency_key,
    )

    if not is_new:
        # Duplicate — already processed this exact event
        logger.debug(f"Duplicate receipt: {receipt.idempotency_key}")
        return DeliveryReceiptResponse(status="duplicate")

    # ── Step 2: Update communication status (forward-only) ──
    extra_kwargs = {}
    if receipt.event_type == "failed":
        extra_kwargs["failure_reason"] = receipt.event_data.get("reason", "unknown")

    status_updated = await campaign_repo.update_communication_status(
        pool=pool,
        comm_id=comm_id,
        status=receipt.event_type,
        **extra_kwargs,
    )

    if status_updated:
        # ── Step 3: Increment campaign counter ──
        campaign_id = await campaign_repo.get_campaign_id_for_communication(pool, comm_id)
        if campaign_id:
            await campaign_repo.increment_campaign_counter(
                pool, campaign_id, receipt.event_type
            )

    logger.info(
        f"Receipt processed: comm={receipt.communication_id[:8]}... "
        f"event={receipt.event_type} new={is_new} status_updated={status_updated}"
    )

    return DeliveryReceiptResponse(status="processed")
