import asyncio
import sys
sys.path.append('crm-service')
from app.database import init_db
from app.config import get_settings

async def main():
    settings = get_settings()
    pool = await init_db(settings.DATABASE_URL)
    async with pool.acquire() as conn:
        # Test 1: Empty tags list
        try:
            row = await conn.fetchrow(
                "SELECT COUNT(*) as count FROM customers WHERE tags @> $1::text[]",
                []
            )
            print("Empty tags success:", dict(row))
        except Exception as e:
            print("Empty tags error:", e)

        # Test 2: Empty cities list
        try:
            row = await conn.fetchrow(
                "SELECT COUNT(*) as count FROM customers WHERE city = ANY($1::text[])",
                []
            )
            print("Empty cities success:", dict(row))
        except Exception as e:
            print("Empty cities error:", e)

asyncio.run(main())
