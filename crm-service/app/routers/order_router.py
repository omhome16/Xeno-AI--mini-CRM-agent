"""
Order API Router — Endpoints for order data ingestion.

Endpoints:
  POST /api/orders         — Bulk import orders
  GET  /api/orders/:cid    — Get orders for a customer
"""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.database import get_main_pool
from app.models.order import OrderBulkImport, OrderResponse
from app.models.customer import BulkImportResponse
from app.repositories import order_repo, customer_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orders", tags=["Orders"])


@router.post(
    "",
    response_model=BulkImportResponse,
    status_code=201,
    summary="Bulk import orders",
    description=(
        "Import orders and automatically update customer aggregates. "
        "Orders can reference customers by customer_id or customer_external_id."
    ),
)
async def bulk_import_orders(payload: OrderBulkImport):
    """
    Bulk import orders into the CRM.

    Each order is linked to a customer by either:
      - customer_id (UUID) — direct reference
      - customer_external_id — resolved to UUID via lookup

    After import, affected customer aggregates (total_orders, total_spent,
    avg_order_value, last_order_at) are automatically recalculated.
    """
    pool = get_main_pool()

    # Resolve customer_external_id to customer_id where needed
    orders_data = []
    resolve_errors = []

    for i, order in enumerate(payload.orders):
        order_dict = order.model_dump()

        if order_dict.get("customer_id") is None and order_dict.get("customer_external_id"):
            # Look up customer by external_id
            customer = await customer_repo.get_customer_by_external_id(
                pool, order_dict["customer_external_id"]
            )
            if customer:
                order_dict["customer_id"] = customer["id"]
            else:
                resolve_errors.append(
                    f"Row {i}: customer_external_id '{order_dict['customer_external_id']}' not found"
                )
                continue

        if order_dict.get("customer_id") is None:
            resolve_errors.append(f"Row {i}: missing customer_id or customer_external_id")
            continue

        # Remove the external_id field before inserting
        order_dict.pop("customer_external_id", None)
        orders_data.append(order_dict)

    # Bulk insert resolved orders
    imported, insert_errors = await order_repo.bulk_insert_orders(pool, orders_data)

    all_errors = resolve_errors + insert_errors
    logger.info(f"Order import: {imported} imported, {len(all_errors)} errors")

    return BulkImportResponse(
        imported=imported,
        errors=len(all_errors),
        error_details=all_errors[:20],
    )


@router.get(
    "/customer/{customer_id}",
    response_model=list[OrderResponse],
    summary="Get orders by customer",
)
async def get_customer_orders(
    customer_id: UUID,
    limit: int = Query(50, ge=1, le=200),
):
    """Fetch order history for a specific customer."""
    pool = get_main_pool()
    orders = await order_repo.get_orders_by_customer(pool, customer_id, limit)
    return [OrderResponse(**o) for o in orders]
