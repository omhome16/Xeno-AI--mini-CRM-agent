import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5433/xeno_crm")
    try:
        total_bangalore = await conn.fetchval("SELECT COUNT(*) FROM customers WHERE city = 'Bangalore'")
        vip_bangalore = await conn.fetchval("SELECT COUNT(*) FROM customers WHERE city = 'Bangalore' AND 'vip' = ANY(tags)")
        total_customers = await conn.fetchval("SELECT COUNT(*) FROM customers")
        total_vip = await conn.fetchval("SELECT COUNT(*) FROM customers WHERE 'vip' = ANY(tags)")
        
        print(f"Total Customers: {total_customers}")
        print(f"Total VIP Customers: {total_vip}")
        print(f"Total Bangalore Customers: {total_bangalore}")
        print(f"VIP Bangalore Customers: {vip_bangalore}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
