import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5433/xeno_crm")
    try:
        campaigns = await conn.fetch("SELECT id, name, status, total_audience, total_sent, total_delivered, total_opened, total_clicked, total_conversions, total_attributed_revenue FROM campaigns")
        print("CAMPAIGNS:")
        for c in campaigns:
            print(dict(c))
        
        comms_stats = await conn.fetch("SELECT status, COUNT(*), SUM(attributed_revenue) FROM communications GROUP BY status")
        print("\nCOMMUNICATION STATUS COUNTS:")
        for s in comms_stats:
            print(dict(s))
            
        events = await conn.fetch("SELECT event_type, COUNT(*) FROM delivery_events GROUP BY event_type")
        print("\nDELIVERY EVENTS COUNTS:")
        for e in events:
            print(dict(e))

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
