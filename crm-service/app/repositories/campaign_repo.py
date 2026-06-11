"""
Campaign Repository — Data access layer for campaigns, communications, delivery_events.
"""

import logging
from typing import Optional, Any
from uuid import UUID

import asyncpg

logger = logging.getLogger(__name__)


# ══════════════════════════════════════
# SEGMENTS
# ══════════════════════════════════════

async def create_segment(
    pool: asyncpg.Pool, name: str, description: str, filter_criteria: dict, customer_count: int
) -> UUID:
    """Create a new segment definition."""
    async with pool.acquire() as conn:
        import json
        row = await conn.fetchrow(
            """
            INSERT INTO segments (name, description, filter_criteria, customer_count)
            VALUES ($1, $2, $3::jsonb, $4)
            RETURNING id
            """,
            name, description, json.dumps(filter_criteria), customer_count,
        )
        return row["id"]


async def get_segment(pool: asyncpg.Pool, segment_id: UUID) -> Optional[dict]:
    """Fetch a segment by ID."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM segments WHERE id = $1", segment_id)
        return dict(row) if row else None


# ══════════════════════════════════════
# CAMPAIGNS
# ══════════════════════════════════════

async def create_campaign(
    pool: asyncpg.Pool,
    name: str,
    segment_id: UUID,
    channel: str,
    message_template: str,
    total_audience: int,
) -> UUID:
    """Create a new campaign."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO campaigns (name, segment_id, channel, message_template,
                                   status, total_audience)
            VALUES ($1, $2, $3, $4, 'sending', $5)
            RETURNING id
            """,
            name, segment_id, channel, message_template, total_audience,
        )
        return row["id"]


async def get_campaign(pool: asyncpg.Pool, campaign_id: UUID) -> Optional[dict]:
    """Fetch a campaign by ID."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT c.*, s.description as segment_description, s.filter_criteria
            FROM campaigns c
            LEFT JOIN segments s ON c.segment_id = s.id
            WHERE c.id = $1
            """,
            campaign_id
        )
        return dict(row) if row else None


async def get_campaigns(pool: asyncpg.Pool, limit: int = 50) -> list[dict]:
    """Fetch all campaigns, most recent first."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT c.*, s.description as segment_description, s.filter_criteria
            FROM campaigns c
            LEFT JOIN segments s ON c.segment_id = s.id
            ORDER BY c.created_at DESC
            LIMIT $1
            """,
            limit
        )
    return [dict(r) for r in rows]


async def update_campaign_status(
    pool: asyncpg.Pool, campaign_id: UUID, status: str
) -> None:
    """Update campaign status."""
    async with pool.acquire() as conn:
        timestamp_field = "started_at" if status == "sending" else "completed_at"
        await conn.execute(
            f"UPDATE campaigns SET status = $1, {timestamp_field} = NOW() WHERE id = $2",
            status, campaign_id,
        )


async def increment_campaign_counter(
    pool: asyncpg.Pool, campaign_id: UUID, event_type: str
) -> None:
    """
    Increment a denormalized counter on the campaigns table.
    Called when a delivery event is processed.
    """
    counter_map = {
        "sent": "total_sent",
        "delivered": "total_delivered",
        "failed": "total_failed",
        "opened": "total_opened",
        "clicked": "total_clicked",
    }
    counter_field = counter_map.get(event_type)
    if not counter_field:
        return

    async with pool.acquire() as conn:
        await conn.execute(
            f"UPDATE campaigns SET {counter_field} = {counter_field} + 1 WHERE id = $1",
            campaign_id,
        )


# ══════════════════════════════════════
# COMMUNICATIONS
# ══════════════════════════════════════

async def create_communication(
    pool: asyncpg.Pool,
    campaign_id: UUID,
    customer_id: UUID,
    channel: str,
    message_content: str,
) -> UUID:
    """Create a single communication record."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO communications (campaign_id, customer_id, channel, message_content)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            campaign_id, customer_id, channel, message_content,
        )
        return row["id"]


async def bulk_create_communications(
    pool: asyncpg.Pool,
    campaign_id: UUID,
    customers: list[dict],
    channel: str,
    message_template: str,
) -> list[UUID]:
    """
    Create communication records for all customers in a campaign.
    Returns list of communication IDs.
    """
    comm_ids = []
    async with pool.acquire() as conn:
        for customer in customers:
            # Simple personalization
            message = message_template.replace("{{name}}", customer.get("name", "there"))
            message = message.replace("{{city}}", customer.get("city", "your city"))

            row = await conn.fetchrow(
                """
                INSERT INTO communications (campaign_id, customer_id, channel, message_content)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                campaign_id, customer["id"], channel, message,
            )
            comm_ids.append(row["id"])
    return comm_ids


async def get_communication(pool: asyncpg.Pool, comm_id: UUID) -> Optional[dict]:
    """Fetch a communication by ID."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM communications WHERE id = $1", comm_id)
        return dict(row) if row else None


async def update_communication_status(
    pool: asyncpg.Pool, comm_id: UUID, status: str, **kwargs
) -> bool:
    """
    Update communication status with forward-only enforcement.
    Returns True if the status was updated, False if rejected (out-of-order).
    """
    STATUS_ORDER = {"pending": 0, "sent": 1, "delivered": 2, "opened": 3, "clicked": 4}

    async with pool.acquire() as conn:
        current = await conn.fetchval(
            "SELECT status FROM communications WHERE id = $1", comm_id
        )
        if current is None:
            return False

        # Failed is terminal from any state
        if status == "failed":
            await conn.execute(
                """
                UPDATE communications
                SET status = 'failed', failed_at = NOW(), failure_reason = $1
                WHERE id = $2
                """,
                kwargs.get("failure_reason", "unknown"), comm_id,
            )
            return True

        # Forward-only: only advance the status
        if STATUS_ORDER.get(status, -1) <= STATUS_ORDER.get(current, -1):
            logger.warning(
                f"Out-of-order event rejected: comm={comm_id}, "
                f"current={current}, received={status}"
            )
            return False

        timestamp_field = f"{status}_at"
        await conn.execute(
            f"UPDATE communications SET status = $1, {timestamp_field} = NOW() WHERE id = $2",
            status, comm_id,
        )
        return True


# ══════════════════════════════════════
# DELIVERY EVENTS
# ══════════════════════════════════════

async def insert_delivery_event(
    pool: asyncpg.Pool,
    communication_id: UUID,
    event_type: str,
    event_data: dict,
    idempotency_key: str,
) -> bool:
    """
    Insert a delivery event. Returns True if inserted, False if duplicate.

    The UNIQUE constraint on idempotency_key provides atomic deduplication —
    no race conditions possible, unlike application-level check-then-insert.
    """
    async with pool.acquire() as conn:
        try:
            import json
            await conn.execute(
                """
                INSERT INTO delivery_events (communication_id, event_type, event_data, idempotency_key)
                VALUES ($1, $2, $3::jsonb, $4)
                """,
                communication_id, event_type, json.dumps(event_data), idempotency_key,
            )
            return True
        except asyncpg.UniqueViolationError:
            # Duplicate — already processed this exact event
            return False


async def get_campaign_id_for_communication(
    pool: asyncpg.Pool, comm_id: UUID
) -> Optional[UUID]:
    """Get the campaign_id for a communication."""
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT campaign_id FROM communications WHERE id = $1", comm_id
        )
