import sys
import os
import asyncio
import asyncpg

# Add parent dir to path so we can import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.schema import SCHEMA_STATEMENTS

async def main():
    conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5433/xeno_crm")
    try:
        print("Running schema updates...")
        for stmt in SCHEMA_STATEMENTS:
            await conn.execute(stmt)
        print("Schema successfully updated!")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
