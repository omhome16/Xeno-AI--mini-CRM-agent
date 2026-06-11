import io
import csv
import logging
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_main_pool

router = APIRouter(prefix="/api/ingest", tags=["Data Ingestion"])

class IngestRequest(BaseModel):
    csv_text: str

@router.post("/customers")
async def ingest_customers(req: IngestRequest):
    """
    Ingest a CSV list of customers.
    CSV headers: name, city, tags, external_id, email, phone
    """
    logger = logging.getLogger(__name__)
    f = io.StringIO(req.csv_text.strip())
    reader = csv.DictReader(f)
    
    if not reader.fieldnames or "name" not in reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV must contain at least a 'name' header")

    pool = get_main_pool()
    inserted_count = 0
    errors = []

    async with pool.acquire() as conn:
        async with conn.transaction():
            for row_idx, row in enumerate(reader, start=1):
                try:
                    name = row.get("name", "").strip()
                    if not name:
                        errors.append(f"Row {row_idx}: 'name' is empty, skipping.")
                        continue
                    
                    external_id = row.get("external_id", "").strip() or None
                    email = row.get("email", "").strip() or None
                    phone = row.get("phone", "").strip() or None
                    city = row.get("city", "").strip() or "Unknown"
                    
                    tags_raw = row.get("tags", "").strip()
                    tags = [t.strip().lower() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
                    
                    # Upsert based on external_id if present, otherwise insert
                    if external_id:
                        await conn.execute(
                            """
                            INSERT INTO customers (external_id, name, email, phone, city, tags)
                            VALUES ($1, $2, $3, $4, $5, $6::text[])
                            ON CONFLICT (external_id) DO UPDATE 
                            SET name = EXCLUDED.name, email = EXCLUDED.email, phone = EXCLUDED.phone, 
                                city = EXCLUDED.city, tags = EXCLUDED.tags, updated_at = NOW()
                            """,
                            external_id, name, email, phone, city, tags
                        )
                    else:
                        await conn.execute(
                            """
                            INSERT INTO customers (name, email, phone, city, tags)
                            VALUES ($1, $2, $3, $4, $5::text[])
                            """,
                            name, email, phone, city, tags
                        )
                    inserted_count += 1
                except Exception as e:
                    errors.append(f"Row {row_idx}: {e}")
                    logger.warning(f"Row {row_idx} ingestion failed: {e}")

    return {
        "status": "success" if not errors else "partial_success",
        "count": inserted_count,
        "message": f"Successfully ingested {inserted_count} customers.",
        "errors": errors
    }

@router.post("/orders")
async def ingest_orders(req: IngestRequest):
    """
    Ingest a CSV list of orders and recompute customer statistics.
    CSV headers: customer_external_id, total_amount, order_date, items_count, category, product_name
    """
    logger = logging.getLogger(__name__)
    f = io.StringIO(req.csv_text.strip())
    reader = csv.DictReader(f)
    
    if not reader.fieldnames or "customer_external_id" not in reader.fieldnames or "total_amount" not in reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV must contain 'customer_external_id' and 'total_amount' headers")

    pool = get_main_pool()
    inserted_count = 0
    errors = []
    affected_customer_external_ids = set()

    async with pool.acquire() as conn:
        async with conn.transaction():
            for row_idx, row in enumerate(reader, start=1):
                try:
                    ext_id = row.get("customer_external_id", "").strip()
                    if not ext_id:
                        errors.append(f"Row {row_idx}: 'customer_external_id' is missing.")
                        continue
                    
                    # Resolve customer_id
                    cust_row = await conn.fetchrow("SELECT id FROM customers WHERE external_id = $1", ext_id)
                    if not cust_row:
                        errors.append(f"Row {row_idx}: Customer with external_id '{ext_id}' not found. Ingest the customer first!")
                        continue
                    
                    customer_id = cust_row["id"]
                    
                    try:
                        total_amount = float(row.get("total_amount", 0))
                    except ValueError:
                        errors.append(f"Row {row_idx}: Invalid total_amount.")
                        continue
                    
                    order_date_str = row.get("order_date", "").strip()
                    if order_date_str:
                        try:
                            # Try various date formats
                            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y"):
                                try:
                                    order_date = datetime.strptime(order_date_str, fmt)
                                    break
                                except ValueError:
                                    continue
                            else:
                                order_date = datetime.fromisoformat(order_date_str)
                        except Exception:
                            order_date = datetime.now()
                    else:
                        order_date = datetime.now()
                        
                    items_count = int(row.get("items_count", "1") or "1")
                    category = row.get("category", "").strip() or None
                    product_name = row.get("product_name", "").strip() or None
                    
                    await conn.execute(
                        """
                        INSERT INTO orders (customer_id, order_date, total_amount, items_count, status, category, product_name)
                        VALUES ($1, $2, $3, $4, 'completed', $5, $6)
                        """,
                        customer_id, order_date, total_amount, items_count, category, product_name
                    )
                    
                    inserted_count += 1
                    affected_customer_external_ids.add(ext_id)
                except Exception as e:
                    errors.append(f"Row {row_idx}: {e}")
                    logger.warning(f"Row {row_idx} order ingestion failed: {e}")

            # Recompute aggregated stats for affected customers
            for ext_id in affected_customer_external_ids:
                try:
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
                        WHERE c.id = stats.customer_id AND c.external_id = $1
                        """,
                        ext_id
                    )
                except Exception as e:
                    logger.error(f"Failed to update customer stats for external_id {ext_id}: {e}")

    return {
        "status": "success" if not errors else "partial_success",
        "count": inserted_count,
        "message": f"Successfully ingested {inserted_count} orders.",
        "errors": errors
    }
