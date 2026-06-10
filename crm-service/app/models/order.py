"""
Order Pydantic models — API request/response schemas.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Request Models ──

class OrderCreate(BaseModel):
    """Schema for creating a single order."""
    customer_id: Optional[UUID] = None
    customer_external_id: Optional[str] = None  # Alternative lookup
    order_date: datetime
    total_amount: float = Field(..., gt=0)
    items_count: int = Field(default=1, ge=1)
    status: str = "completed"


class OrderBulkImport(BaseModel):
    """Schema for bulk importing orders."""
    orders: list[OrderCreate] = Field(..., min_length=1, max_length=10000)


# ── Response Models ──

class OrderResponse(BaseModel):
    """Order data returned in API responses."""
    id: UUID
    customer_id: UUID
    order_date: datetime
    total_amount: float
    items_count: int
    status: str
    created_at: datetime
