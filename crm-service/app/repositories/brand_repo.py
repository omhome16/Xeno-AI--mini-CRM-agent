import json
import logging
from typing import Optional
import asyncpg

logger = logging.getLogger(__name__)

async def get_brand_profile(pool: asyncpg.Pool) -> Optional[dict]:
    """Fetch the brand profile."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT data FROM brand_profile ORDER BY id DESC LIMIT 1")
        if row:
            # If row["data"] is string, load it. asyncpg handles jsonb as dict/list or string depending on setup
            data = row["data"]
            if isinstance(data, str):
                return json.loads(data)
            return data
        return None

async def upsert_brand_profile(pool: asyncpg.Pool, data: dict) -> dict:
    """Save or update the brand profile."""
    async with pool.acquire() as conn:
        # Check if a profile exists
        existing = await conn.fetchval("SELECT id FROM brand_profile ORDER BY id DESC LIMIT 1")
        
        # Serialize the json data to ensure consistency
        serialized_data = json.dumps(data)
        
        if existing:
            await conn.execute(
                "UPDATE brand_profile SET data = $1::jsonb, updated_at = NOW() WHERE id = $2",
                serialized_data, existing
            )
        else:
            await conn.execute(
                "INSERT INTO brand_profile (data) VALUES ($1::jsonb)",
                serialized_data
            )
        return data
