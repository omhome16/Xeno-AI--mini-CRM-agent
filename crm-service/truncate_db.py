import asyncio
import asyncpg
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

async def main():
    # Priority: Command line argument -> Environment variable
    database_url = None
    if len(sys.argv) > 1:
        database_url = sys.argv[1]
    else:
        database_url = os.getenv("DATABASE_URL")
        
    if not database_url:
        print("Error: DATABASE_URL not found in environment or passed as an argument.")
        print("Usage: python truncate_db.py [DATABASE_URL]")
        return
        
    print(f"Connecting to database: {database_url}")
    try:
        conn = await asyncpg.connect(database_url)
        print("Successfully connected.")
        
        # We truncate all tables related to CRM events and data
        print("Truncating customers, orders, communications, delivery_events, campaigns, and segments tables...")
        await conn.execute("TRUNCATE TABLE customers, orders, communications, delivery_events, campaigns, segments CASCADE")
        print("✓ Successfully truncated all tables.")
        
        await conn.close()
    except Exception as e:
        print(f"Error during truncation: {e}")

if __name__ == "__main__":
    asyncio.run(main())
