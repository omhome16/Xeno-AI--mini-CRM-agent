"""
Customer Repository — Data access layer for the customers table.

Pure SQL queries — no business logic here.
All methods take a connection pool and return raw data or domain models.
"""

import logging
from typing import Any, Optional
from uuid import UUID

import asyncpg

logger = logging.getLogger(__name__)


async def insert_customer(pool: asyncpg.Pool, data: dict) -> Optional[UUID]:
    """
    Insert a single customer. Returns the new customer ID.
    Uses ON CONFLICT for upsert on external_id.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO customers (external_id, name, email, phone, whatsapp_id, city, tags)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (external_id) DO UPDATE SET
                name = EXCLUDED.name,
                email = EXCLUDED.email,
                phone = EXCLUDED.phone,
                whatsapp_id = EXCLUDED.whatsapp_id,
                city = EXCLUDED.city,
                tags = EXCLUDED.tags,
                updated_at = NOW()
            RETURNING id
            """,
            data.get("external_id"),
            data["name"],
            data.get("email"),
            data.get("phone"),
            data.get("whatsapp_id"),
            data.get("city"),
            data.get("tags", []),
        )
        return row["id"] if row else None


async def bulk_insert_customers(
    pool: asyncpg.Pool, customers: list[dict]
) -> tuple[int, list[str]]:
    """
    Bulk insert customers. Returns (success_count, error_messages).
    Each customer is inserted individually with error isolation.
    """
    success = 0
    errors = []
    for i, customer in enumerate(customers):
        try:
            await insert_customer(pool, customer)
            success += 1
        except Exception as e:
            errors.append(f"Row {i}: {str(e)[:100]}")
            logger.warning(f"Failed to insert customer row {i}: {e}")
    return success, errors


async def get_customers(
    pool: asyncpg.Pool,
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
) -> tuple[list[dict], int]:
    """
    Fetch paginated customers with optional search.
    Returns (customers, total_count).
    """
    offset = (page - 1) * limit
    async with pool.acquire() as conn:
        if search:
            search_pattern = f"%{search}%"
            rows = await conn.fetch(
                """
                SELECT * FROM customers
                WHERE name ILIKE $1 OR email ILIKE $1 OR city ILIKE $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                search_pattern, limit, offset,
            )
            total = await conn.fetchval(
                """
                SELECT COUNT(*) FROM customers
                WHERE name ILIKE $1 OR email ILIKE $1 OR city ILIKE $1
                """,
                search_pattern,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM customers ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                limit, offset,
            )
            total = await conn.fetchval("SELECT COUNT(*) FROM customers")

    return [dict(r) for r in rows], total


async def get_customer_by_id(pool: asyncpg.Pool, customer_id: UUID) -> Optional[dict]:
    """Fetch a single customer by ID."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM customers WHERE id = $1", customer_id)
        return dict(row) if row else None


async def get_customer_by_external_id(
    pool: asyncpg.Pool, external_id: str
) -> Optional[dict]:
    """Fetch a single customer by external_id."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM customers WHERE external_id = $1", external_id
        )
        return dict(row) if row else None


async def get_customer_stats(pool: asyncpg.Pool) -> dict:
    """Fetch aggregate statistics about all customers."""
    async with pool.acquire() as conn:
        stats = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as total_customers,
                COALESCE(SUM(total_orders), 0) as total_orders,
                COALESCE(SUM(total_spent), 0) as total_revenue,
                COALESCE(AVG(total_orders), 0) as avg_orders,
                COALESCE(AVG(total_spent), 0) as avg_spend
            FROM customers
            """
        )

        city_rows = await conn.fetch(
            """
            SELECT city, COUNT(*) as count FROM customers
            WHERE city IS NOT NULL
            GROUP BY city ORDER BY count DESC
            """
        )

        tag_rows = await conn.fetch(
            """
            SELECT unnest(tags) as tag, COUNT(*) as count
            FROM customers
            GROUP BY tag ORDER BY count DESC
            """
        )

    return {
        "total_customers": stats["total_customers"],
        "total_orders": stats["total_orders"],
        "total_revenue": float(stats["total_revenue"]),
        "avg_orders_per_customer": round(float(stats["avg_orders"]), 1),
        "avg_spend_per_customer": round(float(stats["avg_spend"]), 2),
        "city_distribution": {r["city"]: r["count"] for r in city_rows},
        "tag_distribution": {r["tag"]: r["count"] for r in tag_rows},
    }


async def update_customer_aggregates(
    pool: asyncpg.Pool, customer_id: UUID
) -> None:
    """
    Recalculate and update denormalized order aggregates for a customer.
    Called after orders are ingested.
    """
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE customers SET
                total_orders = sub.total_orders,
                total_spent = sub.total_spent,
                avg_order_value = sub.avg_order_value,
                last_order_at = sub.last_order_at,
                first_order_at = sub.first_order_at,
                updated_at = NOW()
            FROM (
                SELECT
                    COUNT(*) as total_orders,
                    COALESCE(SUM(total_amount), 0) as total_spent,
                    COALESCE(AVG(total_amount), 0) as avg_order_value,
                    MAX(order_date) as last_order_at,
                    MIN(order_date) as first_order_at
                FROM orders WHERE customer_id = $1
            ) sub
            WHERE customers.id = $1
            """,
            customer_id,
        )
