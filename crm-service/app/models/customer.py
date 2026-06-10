"""
Customer Pydantic models — API request/response schemas.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Request Models ──

class CustomerCreate(BaseModel):
    """Schema for creating a single customer."""
    external_id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = None
    phone: Optional[str] = None
    whatsapp_id: Optional[str] = None
    city: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class CustomerBulkImport(BaseModel):
    """Schema for bulk importing customers."""
    customers: list[CustomerCreate] = Field(..., min_length=1, max_length=5000)


# ── Response Models ──

class CustomerResponse(BaseModel):
    """Customer data returned in API responses."""
    id: UUID
    external_id: Optional[str] = None
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    whatsapp_id: Optional[str] = None
    city: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    total_orders: int = 0
    total_spent: float = 0.0
    avg_order_value: float = 0.0
    last_order_at: Optional[datetime] = None
    first_order_at: Optional[datetime] = None
    created_at: datetime


class CustomerListResponse(BaseModel):
    """Paginated list of customers."""
    customers: list[CustomerResponse]
    total: int
    page: int
    limit: int


class CustomerStatsResponse(BaseModel):
    """Aggregate statistics about all customers."""
    total_customers: int
    total_orders: int
    total_revenue: float
    avg_orders_per_customer: float
    avg_spend_per_customer: float
    city_distribution: dict[str, int]
    tag_distribution: dict[str, int]


class BulkImportResponse(BaseModel):
    """Result of a bulk import operation."""
    imported: int
    errors: int
    error_details: list[str] = Field(default_factory=list)
