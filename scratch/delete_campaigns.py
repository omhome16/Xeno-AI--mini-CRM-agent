import asyncio
import asyncpg
import sys
from uuid import UUID

sys.stdout.reconfigure(encoding='utf-8')

async def main():
    conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5433/xeno_crm")
    try:
        # Get count of campaigns
        campaign_count = await conn.fetchval("SELECT count(*) FROM campaigns")
        if campaign_count == 0:
            print("No campaigns found in database.")
            return

        print(f"Found {campaign_count} campaigns in database.")

        # Get customers who converted in any campaign
        converted_customers = await conn.fetch("""
            SELECT DISTINCT customer_id 
            FROM communications 
            WHERE status = 'converted'
        """)
        converted_customer_ids = [r['customer_id'] for r in converted_customers]
        print(f"Customers to restore aggregates for: {len(converted_customer_ids)}")

        # Delete all campaigns (cascades to communications & delivery_events)
        deleted_campaigns = await conn.execute("DELETE FROM campaigns")
        print(f"Campaigns deletion result: {deleted_campaigns}")

        # Delete campaign-generated orders
        # Campaign orders are generated with non-null product_name and category
        deleted_orders = await conn.execute("""
            DELETE FROM orders 
            WHERE category IS NOT NULL AND product_name IS NOT NULL
        """)
        print(f"Campaign orders deletion result: {deleted_orders}")

        # Restore customer aggregates
        from app.repositories import customer_repo
        
        # We need the app pool or we can temporarily import and instantiate a pool, or just reuse conn inside a dummy pool wrapper
        # Since update_customer_aggregates takes a pool, let's create a minimal pool or modify the database state using a direct connection query
        # Let's inspect customer_repo's implementation: it does async with pool.acquire() as conn:
        # So we can pass a mock pool or just run the queries here directly for each customer!
        # The update query is simple:
        for cid in converted_customer_ids:
            # Recalculate
            await conn.execute(
                """
                UPDATE customers SET
                    total_orders = sub.total_orders,
                    total_spent = sub.total_spent,
                    avg_order_value = sub.avg_order_value,
                    last_order_at = sub.last_order_at,
                    first_order_at = sub.first_order_at,
                    updated_at = NOW()
                FROM (
                    SELECT
                        COUNT(*) as total_orders,
                        COALESCE(SUM(total_amount), 0) as total_spent,
                        COALESCE(AVG(total_amount), 0) as avg_order_value,
                        MAX(order_date) as last_order_at,
                        MIN(order_date) as first_order_at
                    FROM orders WHERE customer_id = $1
                ) sub
                WHERE customers.id = $1
                """,
                cid,
            )

            # Sync tags (lapsed, vip, high_value)
            await conn.execute(
                """
                UPDATE customers
                SET tags = ARRAY(
                  SELECT DISTINCT unnest(array_append(tags, 'lapsed'))
                )
                WHERE id = $1
                  AND last_order_at IS NOT NULL 
                  AND last_order_at < NOW() - INTERVAL '60 days'
                """,
                cid,
            )
            await conn.execute(
                """
                UPDATE customers
                SET tags = ARRAY(
                  SELECT t FROM unnest(tags) t WHERE t != 'lapsed'
                )
                WHERE id = $1
                  AND last_order_at IS NOT NULL 
                  AND last_order_at >= NOW() - INTERVAL '60 days'
                """,
                cid,
            )
            
            # Remove vip/high_value tags if they no longer satisfy criteria
            await conn.execute(
                """
                UPDATE customers
                SET tags = ARRAY(
                  SELECT t FROM unnest(tags) t WHERE t NOT IN ('vip', 'high_value')
                )
                WHERE id = $1
                  AND NOT (total_spent >= 10000 OR total_orders >= 10)
                """,
                cid,
            )
            
            # Re-add if they satisfy criteria
            await conn.execute(
                """
                UPDATE customers
                SET tags = ARRAY(
                  SELECT DISTINCT unnest(array_cat(tags, ARRAY['vip', 'high_value']))
                )
                WHERE id = $1
                  AND (total_spent >= 10000 OR total_orders >= 10)
                """,
                cid,
            )
            print(f"Restored aggregates and tags for customer: {cid}")

        print("All campaign data successfully deleted and customer states cleaned up!")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
