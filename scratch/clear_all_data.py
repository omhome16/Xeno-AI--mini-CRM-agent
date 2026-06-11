import asyncio
import asyncpg
import os
from dotenv import load_dotenv

# Load database url from .env
load_dotenv()
db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/xeno_crm")

async def main():
    print(f"Connecting to database at {db_url}...")
    conn = await asyncpg.connect(db_url)
    try:
        # Truncate all tables and reset serial IDs/sequences
        print("Clearing all data (campaigns, segments, communications, delivery_events, orders, customers, brand_profile)...")
        await conn.execute(
            "TRUNCATE TABLE delivery_events, communications, campaigns, segments, orders, customers, brand_profile RESTART IDENTITY CASCADE;"
        )
        print("[OK] Database cleared successfully! Auto-increment sequences reset.")
    except Exception as e:
        print(f"[FAIL] Failed to clear database: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
