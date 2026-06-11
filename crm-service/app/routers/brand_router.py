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
        # Return default Xeno Wear clothing brand structure
        return {
            "brand_name": "Xeno Wear",
            "niche": "Premium Apparel & Sustainable Fashion",
            "product_catalog": [
                {"name": "Organic Cotton Crewneck", "price": 1850.00, "category": "Apparel", "description": "100% organic cotton comfortable daily wear shirt"},
                {"name": "Sustainable Denim Jacket", "price": 4200.00, "category": "Apparel", "description": "Classic look jacket made from recycled wash denim"},
                {"name": "Merino Wool Knit Sweater", "price": 3500.00, "category": "Knitwear", "description": "Super soft ethically sourced merino wool sweater"},
                {"name": "Minimalist Canvas Sneakers", "price": 2400.00, "category": "Footwear", "description": "Eco-friendly canvas sneakers with recycled rubber soles"},
                {"name": "Recycled Polyester Windbreaker", "price": 2900.00, "category": "Outerwear", "description": "Water-resistant light windbreaker jacket"}
            ],
            "outlets": [
                {"name": "Indiranagar Flagship Outlet", "city": "Bangalore", "address": "100 Feet Road, Indiranagar, Bangalore"},
                {"name": "Connaught Place Store", "city": "Delhi", "address": "Inner Circle, Connaught Place, New Delhi"},
                {"name": "Colaba Causeway Boutique", "city": "Mumbai", "address": "Colaba Causeway, Mumbai"}
            ],
            "campaign_urls": [
                "https://xenowear.com/collections/new-arrivals",
                "https://xenowear.com/pages/about-us"
            ],
            "support_phone": "+91-8888899999",
            "brand_tone": "Modern, Conscious, & Inspiring",
            "custom_context": "We focus on sustainable raw materials, fair trade production practices, and minimalist design styles. Our primary target audience is young professionals who care about ecology, premium quality, and timeless styling. We are running an end-of-season sustainable campaign offering a 15% discount for orders above ₹3,000 using code ECO15."
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
