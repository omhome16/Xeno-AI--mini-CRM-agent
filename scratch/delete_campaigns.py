import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5433/xeno_crm")
    try:
        # Fetch the two most recent campaigns
        rows = await conn.fetch("SELECT id, name, created_at FROM campaigns ORDER BY created_at DESC LIMIT 2")
        
        if not rows:
            print("No campaigns found in the database.")
            return

        print(f"Found {len(rows)} campaigns to delete:")
        for r in rows:
            print(f"- ID: {r['id']} | Name: {r['name']} | Created At: {r['created_at']}")
        
        ids_to_delete = [r['id'] for r in rows]
        
        # Delete campaigns (which cascade deletes communications and delivery events)
        deleted = await conn.execute("DELETE FROM campaigns WHERE id = ANY($1)", ids_to_delete)
        print(f"Successfully deleted. Database result: {deleted}")
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
