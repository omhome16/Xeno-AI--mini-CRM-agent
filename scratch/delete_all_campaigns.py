import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5433/xeno_crm")
    try:
        deleted = await conn.execute("DELETE FROM campaigns")
        print(f"Successfully deleted all campaigns. Database result: {deleted}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
