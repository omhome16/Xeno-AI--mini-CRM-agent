import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5433/xeno_crm")
    try:
        orders_count = await conn.fetchval("SELECT count(*) FROM orders")
        customers_count = await conn.fetchval("SELECT count(*) FROM customers")
        campaigns_count = await conn.fetchval("SELECT count(*) FROM campaigns")
        print(f"Remaining Campaigns: {campaigns_count}")
        print(f"Remaining Customers: {customers_count}")
        print(f"Remaining Orders: {orders_count}")
        
        # Check a sample order to see what its fields look like
        sample = await conn.fetchrow("SELECT * FROM orders LIMIT 1")
        if sample:
            print("Sample Order:", dict(sample))
        else:
            print("No orders left.")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
