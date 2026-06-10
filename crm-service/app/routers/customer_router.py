"""
Customer API Router — Endpoints for customer data management.

Endpoints:
  POST /api/customers         — Bulk import customers
  GET  /api/customers         — List customers (paginated, searchable)
  GET  /api/customers/stats   — Aggregate customer statistics
  GET  /api/customers/:id     — Get single customer by ID
"""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.database import get_main_pool
from app.models.customer import (
    CustomerBulkImport,
    CustomerResponse,
    CustomerListResponse,
    CustomerStatsResponse,
    BulkImportResponse,
)
from app.repositories import customer_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/customers", tags=["Customers"])


@router.post(
    "",
    response_model=BulkImportResponse,
    status_code=201,
    summary="Bulk import customers",
    description="Import up to 5000 customers at once. Uses upsert on external_id.",
)
async def bulk_import_customers(payload: CustomerBulkImport):
    """
    Bulk import customers into the CRM.

    Each customer is upserted — if a customer with the same external_id
    already exists, their profile is updated. This makes the endpoint
    idempotent and safe to call multiple times.
    """
    pool = get_main_pool()
    customers_data = [c.model_dump() for c in payload.customers]

    imported, errors = await customer_repo.bulk_insert_customers(pool, customers_data)

    logger.info(f"Bulk import: {imported} imported, {len(errors)} errors")
    return BulkImportResponse(
        imported=imported,
        errors=len(errors),
        error_details=errors[:20],  # Cap error details to avoid huge responses
    )


@router.get(
    "",
    response_model=CustomerListResponse,
    summary="List customers",
    description="Paginated customer list with optional search across name, email, and city.",
)
async def list_customers(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    search: str = Query(None, description="Search by name, email, or city"),
):
    """Fetch paginated customers with optional search."""
    pool = get_main_pool()
    customers, total = await customer_repo.get_customers(pool, page, limit, search)

    return CustomerListResponse(
        customers=[CustomerResponse(**c) for c in customers],
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/stats",
    response_model=CustomerStatsResponse,
    summary="Customer statistics",
    description="Aggregate statistics: total customers, revenue, city distribution, etc.",
)
async def customer_stats():
    """Fetch aggregate customer statistics."""
    pool = get_main_pool()
    stats = await customer_repo.get_customer_stats(pool)
    return CustomerStatsResponse(**stats)


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Get customer by ID",
)
async def get_customer(customer_id: UUID):
    """Fetch a single customer by their UUID."""
    pool = get_main_pool()
    customer = await customer_repo.get_customer_by_id(pool, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return CustomerResponse(**customer)
