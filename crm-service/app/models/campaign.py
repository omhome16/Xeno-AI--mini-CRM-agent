"""
Campaign & Communication Pydantic models.
"""

from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── Campaign Models ──

class CampaignResponse(BaseModel):
    """Campaign data returned in API responses."""
    id: UUID
    name: str
    segment_id: Optional[UUID] = None
    channel: str
    message_template: str
    status: str
    total_audience: int = 0
    total_sent: int = 0
    total_delivered: int = 0
    total_failed: int = 0
    total_opened: int = 0
    total_clicked: int = 0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class CampaignListResponse(BaseModel):
    """List of campaigns."""
    campaigns: list[CampaignResponse]
    total: int


class CampaignStatsResponse(BaseModel):
    """Detailed campaign analytics."""
    campaign: CampaignResponse
    funnel: dict[str, int]
    delivery_rate: float
    open_rate: float
    click_rate: float
    failure_reasons: dict[str, int]


# ── Communication Models ──

class CommunicationResponse(BaseModel):
    """Individual communication tracking."""
    id: UUID
    campaign_id: UUID
    customer_id: UUID
    channel: str
    status: str
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    created_at: datetime


# ── Delivery Receipt Models ──

class DeliveryReceiptRequest(BaseModel):
    """
    Delivery event callback from the channel service.
    
    The idempotency_key ensures duplicate callbacks are safely ignored
    via a UNIQUE constraint in the delivery_events table.
    """
    communication_id: str
    event_type: str = Field(
        ..., pattern="^(sent|delivered|failed|opened|clicked)$"
    )
    timestamp: Optional[str] = None
    event_data: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str


class DeliveryReceiptResponse(BaseModel):
    """Response to a delivery event callback."""
    status: str  # "processed" or "duplicate"
