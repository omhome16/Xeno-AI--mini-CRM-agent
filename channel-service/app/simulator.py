"""
Delivery Simulator — Simulates realistic message delivery lifecycle.

When the CRM sends a message via POST /api/send, this module spawns an
independent asyncio task that walks through the delivery lifecycle:

    pending → sent → delivered → opened → clicked

Each transition has:
  - A random delay (simulating network/user behavior)
  - A probabilistic outcome (not every message gets opened)
  - A callback fired to the CRM receipt API

Probabilities (realistic for marketing campaigns):
  - Sent:      100% (always reaches the network)
  - Delivered:  90% (10% fail — invalid number, blocked, etc.)
  - Opened:     60% of delivered
  - Clicked:    30% of opened

This gives an overall funnel:
  1000 sent → 900 delivered → 540 opened → 162 clicked
"""

import asyncio
import random
import logging
from uuid import uuid4
from datetime import datetime, timezone
from typing import Optional

from app.callback import fire_callback
from app.config import get_settings

logger = logging.getLogger(__name__)

# ── Failure Reasons (realistic) ──
FAILURE_REASONS = [
    "invalid_number",
    "undeliverable",
    "blocked_by_user",
    "rate_limited",
    "network_timeout",
    "opt_out",
]

# Track active simulation tasks for graceful shutdown
_active_tasks: set[asyncio.Task] = set()


async def simulate_delivery(
    communication_id: str,
    recipient: dict,
    message: str,
    channel: str,
) -> None:
    """
    Simulate the full delivery lifecycle for a single message.

    This runs as an independent asyncio task — non-blocking.
    Each step fires a callback to the CRM receipt API.

    Args:
        communication_id: Unique ID for this communication (from CRM).
        recipient: Contact info (phone, email, whatsapp_id).
        message: The message content.
        channel: Channel type (whatsapp, sms, email, rcs).
    """
    settings = get_settings()
    callback_url = settings.CRM_RECEIPT_URL

    try:
        # ── Step 1: SENT (always, after small network delay) ──
        await asyncio.sleep(random.uniform(0.1, 0.5))
        await fire_callback(callback_url, {
            "communication_id": communication_id,
            "event_type": "sent",
            "timestamp": _now_iso(),
            "idempotency_key": f"{communication_id}-sent-{uuid4().hex[:8]}",
        })
        logger.info(f"[{communication_id[:8]}] SENT via {channel}")

        # ── Step 2: DELIVERED or FAILED (90% success) ──
        await asyncio.sleep(random.uniform(0.5, 3.0))
        if random.random() < 0.90:
            await fire_callback(callback_url, {
                "communication_id": communication_id,
                "event_type": "delivered",
                "timestamp": _now_iso(),
                "idempotency_key": f"{communication_id}-delivered-{uuid4().hex[:8]}",
            })
            logger.info(f"[{communication_id[:8]}] DELIVERED")
        else:
            reason = random.choice(FAILURE_REASONS)
            await fire_callback(callback_url, {
                "communication_id": communication_id,
                "event_type": "failed",
                "timestamp": _now_iso(),
                "event_data": {"reason": reason},
                "idempotency_key": f"{communication_id}-failed-{uuid4().hex[:8]}",
            })
            logger.info(f"[{communication_id[:8]}] FAILED: {reason}")
            return  # Stop lifecycle on failure

        # ── Step 3: OPENED (60% of delivered) ──
        if random.random() < 0.60:
            await asyncio.sleep(random.uniform(2, 15))
            await fire_callback(callback_url, {
                "communication_id": communication_id,
                "event_type": "opened",
                "timestamp": _now_iso(),
                "idempotency_key": f"{communication_id}-opened-{uuid4().hex[:8]}",
            })
            logger.info(f"[{communication_id[:8]}] OPENED")
        else:
            return  # User didn't open

        # ── Step 4: CLICKED (30% of opened) ──
        if random.random() < 0.30:
            await asyncio.sleep(random.uniform(1, 10))
            await fire_callback(callback_url, {
                "communication_id": communication_id,
                "event_type": "clicked",
                "timestamp": _now_iso(),
                "idempotency_key": f"{communication_id}-clicked-{uuid4().hex[:8]}",
            })
            logger.info(f"[{communication_id[:8]}] CLICKED")

    except asyncio.CancelledError:
        logger.warning(f"[{communication_id[:8]}] Simulation cancelled")
    except Exception as e:
        logger.error(f"[{communication_id[:8]}] Simulation error: {e}")


def schedule_delivery(
    communication_id: str,
    recipient: dict,
    message: str,
    channel: str,
) -> asyncio.Task:
    """
    Schedule a delivery simulation as a background task.

    Returns the asyncio.Task so it can be tracked or cancelled.
    """
    task = asyncio.create_task(
        simulate_delivery(communication_id, recipient, message, channel),
        name=f"sim-{communication_id[:8]}",
    )

    # Track for graceful shutdown
    _active_tasks.add(task)
    task.add_done_callback(_active_tasks.discard)

    return task


async def cancel_all_simulations() -> int:
    """
    Cancel all running simulation tasks. Called on shutdown.

    Returns:
        Number of tasks cancelled.
    """
    count = len(_active_tasks)
    for task in _active_tasks:
        task.cancel()
    if _active_tasks:
        await asyncio.gather(*_active_tasks, return_exceptions=True)
    logger.info(f"Cancelled {count} active simulations")
    return count


def _now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()
