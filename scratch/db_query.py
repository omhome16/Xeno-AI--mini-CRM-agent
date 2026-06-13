import asyncio
import asyncpg
import sys

# Set encoding to utf-8 for stdout
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5433/xeno_crm")
    try:
        # Check campaign names and statuses
        campaigns = await conn.fetch("SELECT id, name, total_sent, total_delivered, total_opened, total_clicked, total_conversions, total_attributed_revenue FROM campaigns")
        print("CAMPAIGNS:")
        for r in campaigns:
            campaign_data = dict(r)
            # Ensure safe print of name (replace Rupee symbol if any representation issue)
            campaign_data['name'] = campaign_data['name'].replace('\u20b9', 'Rs.')
            print(campaign_data)

        # Check total delivery event types
        events = await conn.fetch("SELECT event_type, count(*) as count FROM delivery_events GROUP BY event_type")
        print("\nDELIVERY EVENTS:")
        for r in events:
            print(dict(r))

        # Check communication statuses
        comms = await conn.fetch("SELECT status, count(*) as count FROM communications GROUP BY status")
        print("\nCOMMUNICATIONS STATUS SUMMARY:")
        for r in comms:
            print(dict(r))

        # Count communications per campaign and their status
        comp_status = await conn.fetch("""
            SELECT c.name, com.status, count(*) as count 
            FROM communications com 
            JOIN campaigns c ON com.campaign_id = c.id 
            GROUP BY c.name, com.status
            ORDER BY c.name, com.status
        """)
        print("\nSTATUS PER CAMPAIGN:")
        for r in comp_status:
            data = dict(r)
            data['name'] = data['name'].replace('\u20b9', 'Rs.')
            print(data)

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
