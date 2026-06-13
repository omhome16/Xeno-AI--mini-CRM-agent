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
async def list_campaigns(limit: int = 50, offset: int = 0):
    """Fetch campaigns, most recent first, with limit and offset."""
    pool = get_main_pool()
    campaigns, total = await campaign_repo.get_campaigns(pool, limit=limit, offset=offset)
    return CampaignListResponse(
        campaigns=[CampaignResponse(**c) for c in campaigns],
        total=total,
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

    # Calculate funnel and rates safely
    delivery_rate = (
        round(campaign_data.total_delivered / campaign_data.total_sent * 100, 1)
        if campaign_data.total_sent and campaign_data.total_sent > 0
        else 0.0
    )
    open_rate = (
        round(campaign_data.total_opened / campaign_data.total_delivered * 100, 1)
        if campaign_data.total_delivered and campaign_data.total_delivered > 0
        else 0.0
    )
    click_rate = (
        round(campaign_data.total_clicked / campaign_data.total_delivered * 100, 1)
        if campaign_data.total_delivered and campaign_data.total_delivered > 0
        else 0.0
    )

    funnel = {
        "audience": campaign_data.total_audience,
        "sent": campaign_data.total_sent,
        "delivered": campaign_data.total_delivered,
        "opened": campaign_data.total_opened,
        "clicked": campaign_data.total_clicked,
        "failed": campaign_data.total_failed,
    }

    # Populate failure reasons from delivery_events table
    async with pool.acquire() as conn:
        failure_rows = await conn.fetch(
            """
            SELECT de.event_data->>'reason' AS reason, COUNT(*) AS count
            FROM delivery_events de
            JOIN communications c ON c.id = de.communication_id
            WHERE c.campaign_id = $1 AND de.event_type = 'failed'
            GROUP BY reason
            ORDER BY count DESC
            """,
            campaign_id
        )
    failure_reasons = {r["reason"]: r["count"] for r in failure_rows if r["reason"]}

    return CampaignStatsResponse(
        campaign=campaign_data,
        funnel=funnel,
        delivery_rate=delivery_rate,
        open_rate=open_rate,
        click_rate=click_rate,
        failure_reasons=failure_reasons,
    )
