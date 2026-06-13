import asyncio
import asyncpg
from app.config import get_settings
from app.seed.seeder import seed_demo_data

async def main():
    settings = get_settings()
    print(f"Connecting to database: {settings.DATABASE_URL}")
    pool = await asyncpg.create_pool(
        settings.DATABASE_URL,
        min_size=1,
        max_size=5
    )
    
    try:
        async with pool.acquire() as conn:
            # Clean up tables
            print("Truncating customers and orders tables...")
            await conn.execute("TRUNCATE TABLE customers CASCADE")
            print("Successfully truncated tables.")
            
        # Run seed
        print("Running demo data seeder...")
        summary = await seed_demo_data(pool)
        print(f"Database successfully re-seeded: {summary}")
        
    finally:
        await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
