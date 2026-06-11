import asyncio
import csv
import os
import sys
from datetime import datetime
from uuid import uuid4
import asyncpg
from dotenv import load_dotenv

# Load database url from env
load_dotenv()
db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/xeno_crm")

async def main():
    print(f"Connecting to database at {db_url}...")
    conn = await asyncpg.connect(db_url)
    
    try:
        # 1. Truncate database tables
        print("Purging database...")
        await conn.execute(
            "TRUNCATE TABLE delivery_events, communications, campaigns, segments, orders, customers, brand_profile RESTART IDENTITY CASCADE;"
        )
        print("[OK] Database tables truncated.")
        
        # 2. Read customers.csv
        customers_file = "ingestion_templates/customers.csv"
        if not os.path.exists(customers_file):
            print(f"Error: {customers_file} not found.")
            return

        print("Reading customers from CSV...")
        customers_to_insert = []
        external_id_to_uuid = {}
        
        with open(customers_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ext_id = row["external_id"].strip()
                name = row["name"].strip()
                email = row["email"].strip() or None
                phone = row["phone"].strip() or None
                city = row["city"].strip() or "Unknown"
                
                tags_raw = row["tags"].strip()
                tags = [t.strip().lower() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
                
                # Generate new UUID for this customer
                cust_uuid = uuid4()
                external_id_to_uuid[ext_id] = cust_uuid
                
                customers_to_insert.append((
                    cust_uuid,
                    ext_id,
                    name,
                    email,
                    phone,
                    phone,  # whatsapp_id matches phone
                    city,
                    tags
                ))
        
        # 3. Bulk Insert Customers using copy_records_to_table
        print(f"Bulk importing {len(customers_to_insert)} customers...")
        await conn.copy_records_to_table(
            "customers",
            records=customers_to_insert,
            columns=["id", "external_id", "name", "email", "phone", "whatsapp_id", "city", "tags"]
        )
        print("[OK] Customers loaded.")
        
        # 4. Read orders.csv
        orders_file = "ingestion_templates/orders.csv"
        if not os.path.exists(orders_file):
            print(f"Error: {orders_file} not found.")
            return
            
        print("Reading orders from CSV...")
        orders_to_insert = []
        
        with open(orders_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ext_id = row["customer_external_id"].strip()
                if ext_id not in external_id_to_uuid:
                    continue  # Skip order if customer not found
                
                cust_id = external_id_to_uuid[ext_id]
                total_amount = float(row["total_amount"])
                items_count = int(row["items_count"] or 1)
                category = row["category"].strip() or None
                product_name = row["product_name"].strip() or None
                
                order_date_str = row["order_date"].strip()
                order_date = datetime.strptime(order_date_str, "%Y-%m-%d %H:%M:%S")
                
                orders_to_insert.append((
                    cust_id,
                    order_date,
                    total_amount,
                    items_count,
                    "completed",
                    category,
                    product_name
                ))
                
        # 5. Bulk Insert Orders
        print(f"Bulk importing {len(orders_to_insert)} orders...")
        await conn.copy_records_to_table(
            "orders",
            records=orders_to_insert,
            columns=["customer_id", "order_date", "total_amount", "items_count", "status", "category", "product_name"]
        )
        print("[OK] Orders loaded.")
        
        # 6. Bulk update customer aggregates
        print("Recalculating customer metrics in bulk...")
        await conn.execute(
            """
            UPDATE customers c
            SET 
                total_orders = COALESCE(stats.total_orders, 0),
                total_spent = COALESCE(stats.total_spent, 0.00),
                avg_order_value = CASE WHEN COALESCE(stats.total_orders, 0) > 0 
                                       THEN COALESCE(stats.total_spent, 0.00) / stats.total_orders 
                                       ELSE 0.00 END,
                last_order_at = stats.last_order_at,
                first_order_at = stats.first_order_at,
                updated_at = NOW()
            FROM (
                SELECT 
                    customer_id,
                    COUNT(*) as total_orders,
                    SUM(total_amount) as total_spent,
                    MAX(order_date) as last_order_at,
                    MIN(order_date) as first_order_at
                FROM orders
                GROUP BY customer_id
            ) stats
            WHERE c.id = stats.customer_id;
            """
        )
        print("[OK] Customer aggregated aggregates updated.")
        
        # Double check counts
        cust_count = await conn.fetchval("SELECT COUNT(*) FROM customers")
        ord_count = await conn.fetchval("SELECT COUNT(*) FROM orders")
        print(f"\n[SUCCESS] Loaded {cust_count} customers and {ord_count} orders successfully in milliseconds!")
        
    except Exception as e:
        print(f"[ERROR] Import failed: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
