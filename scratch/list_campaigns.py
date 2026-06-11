import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5433/xeno_crm")
    try:
        rows = await conn.fetch("SELECT id, name, created_at, status, total_audience FROM campaigns ORDER BY created_at DESC")
        if not rows:
            print("No campaigns found in the database.")
            return
        print(f"Total campaigns: {len(rows)}")
        for r in rows:
            print(f"- ID: {r['id']} | Name: {r['name']} | Status: {r['status']} | Audience: {r['total_audience']} | Created: {r['created_at']}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
