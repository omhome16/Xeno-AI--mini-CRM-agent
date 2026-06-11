from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from app.database import get_main_pool
from app.repositories import brand_repo

router = APIRouter(prefix="/brand", tags=["Brand Profile"])

class ProductItem(BaseModel):
    name: str
    price: float
    category: Optional[str] = None
    description: Optional[str] = None

class OutletItem(BaseModel):
    name: str
    city: str
    address: Optional[str] = None

class BrandProfileModel(BaseModel):
    brand_name: str = Field(..., example="Keventers Shakes")
    niche: str = Field(..., example="Beverages")
    product_catalog: List[ProductItem] = Field(default_factory=list)
    outlets: List[OutletItem] = Field(default_factory=list)
    campaign_urls: List[str] = Field(default_factory=list)
    support_phone: Optional[str] = None
    brand_tone: Optional[str] = "Friendly & Enthusiastic"
    custom_context: Optional[str] = None

@router.get("")
async def get_profile():
    """Fetch the saved Brand Profile context. Returns defaults if empty."""
    pool = get_main_pool()
    profile = await brand_repo.get_brand_profile(pool)
    if not profile:
        # Return sensible default structure
        return {
            "brand_name": "Demo Retail Brand",
            "niche": "Retail & D2C",
            "product_catalog": [],
            "outlets": [],
            "campaign_urls": [],
            "support_phone": "+91-9999999999",
            "brand_tone": "Warm & Professional",
            "custom_context": ""
        }
    return profile

@router.post("")
async def save_profile(profile: BrandProfileModel):
    """Save/update the Brand Profile context."""
    pool = get_main_pool()
    try:
        data = profile.dict()
        result = await brand_repo.upsert_brand_profile(pool, data)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save profile: {e}")
