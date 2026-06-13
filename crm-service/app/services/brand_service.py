import logging
from app.database import get_main_pool
from app.repositories import brand_repo

logger = logging.getLogger(__name__)

async def fetch_brand_profile_ctx() -> str:
    """
    Fetch the brand profile from the database and format it as plain text.
    """
    try:
        pool = get_main_pool()
        profile = await brand_repo.get_brand_profile(pool)
        if not profile:
            return "No brand profile configured. Apply general retail best practices."

        lines = [
            f"Brand Name: {profile.get('brand_name', 'Unknown')}",
            f"Category/Niche: {profile.get('niche', 'Retail')}",
            f"Tone of Voice: {profile.get('brand_tone', 'Professional')}",
        ]

        catalog = profile.get("product_catalog", [])
        if catalog:
            lines.append("Products:")
            for p in catalog:
                lines.append(
                    f"  - {p.get('name')} | ₹{p.get('price')} | "
                    f"{p.get('category', '')} | {p.get('description', '')}"
                )

        outlets = profile.get("outlets", [])
        if outlets:
            lines.append("Store Locations:")
            for o in outlets:
                lines.append(f"  - {o.get('name')}, {o.get('city')}: {o.get('address', '')}")

        urls = profile.get("campaign_urls", [])
        if urls:
            lines.append("Campaign URLs / CTAs:")
            for u in urls:
                lines.append(f"  - {u}")

        if profile.get("support_phone"):
            lines.append(f"Support Phone: {profile.get('support_phone')}")

        if profile.get("custom_context"):
            lines.append(f"Brand Notes: {profile.get('custom_context')}")

        return "\n".join(lines)

    except Exception as e:
        logger.warning(f"[fetch_brand_profile_ctx] Failed to fetch brand profile: {e}")
        return "No brand profile available."
