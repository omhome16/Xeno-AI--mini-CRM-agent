"""
Campaign Worker — Dispatches campaign messages to the channel service.

When a campaign is executed, this worker:
  1. Fetches all communication records for the campaign
  2. Sends each message to the channel service via HTTP
  3. Streams progress updates via SSE
  4. Marks the campaign as completed when done

Rate limiting: Sends messages in batches to avoid overwhelming
the channel service (configurable batch size and delay).
"""

import asyncio
import logging
from uuid import UUID
from typing import Optional

import httpx

from app.config import get_settings
from app.database import get_main_pool
from app.repositories import campaign_repo
from app.sse.manager import push_event

logger = logging.getLogger(__name__)

# ── Worker Configuration ──
BATCH_SIZE = 50          # Messages per batch
BATCH_DELAY_S = 0.5      # Delay between batches
SEND_TIMEOUT_S = 10.0    # Timeout per send request


async def dispatch_campaign(
    campaign_id: str,
    conversation_id: Optional[str] = None,
) -> dict:
    """
    Dispatch all messages for a campaign to the channel service.

    Flow:
      1. Fetch campaign + communications from DB
      2. Send each communication to channel service
      3. Update campaign status (sending → completed)
      4. Stream progress via SSE

    Args:
        campaign_id: UUID of the campaign to dispatch.
        conversation_id: Optional SSE conversation to stream progress.

    Returns:
        Summary dict with sent/failed counts.
    """
    settings = get_settings()
    pool = get_main_pool()
    cid = UUID(campaign_id)

    # Fetch campaign
    campaign = await campaign_repo.get_campaign(pool, cid)
    if not campaign:
        return {"error": f"Campaign {campaign_id} not found"}

    # Update status to sending
    await campaign_repo.update_campaign_status(pool, cid, "sending")

    # Fetch all pending communication IDs for this campaign (lightweight)
    async with pool.acquire() as conn:
        comm_ids = await conn.fetch(
            """
            SELECT id FROM communications
            WHERE campaign_id = $1 AND status = 'pending'
            ORDER BY created_at
            """,
            cid,
        )

    total = len(comm_ids)
    sent = 0
    failed = 0

    if conversation_id:
        await push_event(conversation_id, "campaign_update", {
            "campaign_id": campaign_id,
            "status": "dispatching",
            "total": total,
            "sent": 0,
            "progress_pct": 0,
        })

    # Send in batches
    async with httpx.AsyncClient(timeout=SEND_TIMEOUT_S) as client:
        for i in range(0, total, BATCH_SIZE):
            batch_ids = [r["id"] for r in comm_ids[i:i + BATCH_SIZE]]
            async with pool.acquire() as conn:
                batch = await conn.fetch(
                    """
                    SELECT c.id, c.customer_id, c.channel, c.message_content,
                           cust.phone, cust.email, cust.whatsapp_id, cust.name
                    FROM communications c
                    JOIN customers cust ON cust.id = c.customer_id
                    WHERE c.id = ANY($1::uuid[])
                    ORDER BY c.created_at
                    """,
                    batch_ids,
                )

            for comm in batch:
                try:
                    response = await client.post(
                        settings.CHANNEL_SERVICE_URL,
                        json={
                            "communication_id": str(comm["id"]),
                            "recipient": {
                                "phone": comm["phone"],
                                "email": comm["email"],
                                "whatsapp_id": comm["whatsapp_id"],
                            },
                            "message": comm["message_content"],
                            "channel": comm["channel"],
                        },
                    )

                    if response.status_code == 202:
                        sent += 1
                    else:
                        failed += 1
                        logger.warning(
                            f"Channel service rejected: comm={str(comm['id'])[:8]}, "
                            f"status={response.status_code}"
                        )
                        # Mark failed dispatch in DB (Issue 8)
                        async with pool.acquire() as conn:
                            await conn.execute(
                                """
                                UPDATE communications
                                SET status = 'failed', failed_at = NOW(), failure_reason = $1
                                WHERE id = $2
                                """,
                                f"Channel service rejected: HTTP {response.status_code}", comm["id"]
                            )
                            await conn.execute(
                                "UPDATE campaigns SET total_failed = total_failed + 1 WHERE id = $1",
                                cid
                            )

                except Exception as e:
                    failed += 1
                    logger.error(f"Failed to dispatch comm={str(comm['id'])[:8]}: {e}")
                    # Mark failed dispatch in DB (Issue 8)
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """
                            UPDATE communications
                            SET status = 'failed', failed_at = NOW(), failure_reason = $1
                            WHERE id = $2
                            """,
                            f"Dispatch error: {str(e)[:200]}", comm["id"]
                        )
                        await conn.execute(
                            "UPDATE campaigns SET total_failed = total_failed + 1 WHERE id = $1",
                            cid
                        )

            # Progress update (indented inside loop!) (Issue 1)
            progress = min(100, round((i + len(batch)) / total * 100))
            if conversation_id:
                await push_event(conversation_id, "campaign_update", {
                    "campaign_id": campaign_id,
                    "status": "dispatching",
                    "total": total,
                    "sent": sent,
                    "failed": failed,
                    "progress_pct": progress,
                })

            # Rate limit between batches (indented inside loop!) (Issue 1)
            if i + BATCH_SIZE < total:
                await asyncio.sleep(BATCH_DELAY_S)

    # Mark campaign as completed
    await campaign_repo.update_campaign_status(pool, cid, "completed")

    summary = {
        "campaign_id": campaign_id,
        "status": "completed",
        "total": total,
        "dispatched": sent,
        "failed": failed,
    }

    if conversation_id:
        await push_event(conversation_id, "campaign_update", {
            **summary,
            "progress_pct": 100,
        })

    logger.info(
        f"Campaign {campaign_id[:8]} dispatch complete: "
        f"{sent}/{total} sent, {failed} failed"
    )
    return summary
