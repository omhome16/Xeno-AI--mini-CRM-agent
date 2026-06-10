"""
Order Repository — Data access layer for the orders table.
"""

import logging
from typing import Optional
from uuid import UUID

import asyncpg

logger = logging.getLogger(__name__)


async def insert_order(pool: asyncpg.Pool, data: dict) -> Optional[UUID]:
    """Insert a single order. Returns the new order ID."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO orders (customer_id, order_date, total_amount, items_count, status)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            data["customer_id"],
            data["order_date"],
            data["total_amount"],
            data.get("items_count", 1),
            data.get("status", "completed"),
        )
        return row["id"] if row else None


async def bulk_insert_orders(
    pool: asyncpg.Pool, orders: list[dict]
) -> tuple[int, list[str]]:
    """
    Bulk insert orders. Returns (success_count, error_messages).
    Also updates customer aggregates after each successful insert.
    """
    from app.repositories.customer_repo import update_customer_aggregates

    success = 0
    errors = []
    customer_ids_to_update = set()

    for i, order in enumerate(orders):
        try:
            await insert_order(pool, order)
            customer_ids_to_update.add(order["customer_id"])
            success += 1
        except Exception as e:
            errors.append(f"Row {i}: {str(e)[:100]}")
            logger.warning(f"Failed to insert order row {i}: {e}")

    # Update aggregates for all affected customers
    for cid in customer_ids_to_update:
        try:
            await update_customer_aggregates(pool, cid)
        except Exception as e:
            logger.error(f"Failed to update aggregates for customer {cid}: {e}")

    return success, errors


async def get_orders_by_customer(
    pool: asyncpg.Pool, customer_id: UUID, limit: int = 50
) -> list[dict]:
    """Fetch orders for a specific customer."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM orders
            WHERE customer_id = $1
            ORDER BY order_date DESC
            LIMIT $2
            """,
            customer_id, limit,
        )
    return [dict(r) for r in rows]
