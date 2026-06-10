"""
Campaign API Router — Campaign management and analytics.

Endpoints:
  GET  /api/campaigns           — List all campaigns
  GET  /api/campaigns/:id       — Get campaign details with analytics
"""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.database import get_main_pool
from app.models.campaign import CampaignResponse, CampaignListResponse, CampaignStatsResponse
from app.repositories import campaign_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/campaigns", tags=["Campaigns"])


@router.get(
    "",
    response_model=CampaignListResponse,
    summary="List all campaigns",
)
async def list_campaigns():
    """Fetch all campaigns, most recent first."""
    pool = get_main_pool()
    campaigns = await campaign_repo.get_campaigns(pool)
    return CampaignListResponse(
        campaigns=[CampaignResponse(**c) for c in campaigns],
        total=len(campaigns),
    )


@router.get(
    "/{campaign_id}",
    response_model=CampaignStatsResponse,
    summary="Get campaign details with analytics",
)
async def get_campaign_details(campaign_id: UUID):
    """
    Fetch detailed campaign info with analytics.

    Returns:
      - Campaign metadata
      - Delivery funnel (sent → delivered → opened → clicked)
      - Calculated rates (delivery rate, open rate, click rate)
      - Failure reasons breakdown
    """
    pool = get_main_pool()
    campaign = await campaign_repo.get_campaign(pool, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign_data = CampaignResponse(**campaign)

    # Calculate funnel and rates
    total_sent = campaign_data.total_sent or 1  # Avoid division by zero
    total_delivered = campaign_data.total_delivered or 1

    funnel = {
        "audience": campaign_data.total_audience,
        "sent": campaign_data.total_sent,
        "delivered": campaign_data.total_delivered,
        "opened": campaign_data.total_opened,
        "clicked": campaign_data.total_clicked,
        "failed": campaign_data.total_failed,
    }

    return CampaignStatsResponse(
        campaign=campaign_data,
        funnel=funnel,
        delivery_rate=round(campaign_data.total_delivered / total_sent * 100, 1),
        open_rate=round(campaign_data.total_opened / total_delivered * 100, 1),
        click_rate=round(campaign_data.total_clicked / total_delivered * 100, 1),
        failure_reasons={},  # Will be populated from delivery_events in a future enhancement
    )
