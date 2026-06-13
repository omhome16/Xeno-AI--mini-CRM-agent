import asyncio
import json
import logging
from uuid import UUID
from app.services.redis_queue import pop_from_queue
from app.database import get_main_pool

logger = logging.getLogger(__name__)

async def start_receipt_worker():
    """Background worker that pops events from crm_receipt_queue and processes them."""
    logger.info("Receipt Worker started.")
    pool = get_main_pool()
    if not pool:
        logger.error("Database pool not initialized. Receipt worker cannot start.")
        return

    while True:
        try:
            # Block pop a receipt from the queue
            tasks = []
            first_task = await asyncio.to_thread(pop_from_queue, "crm_receipt_queue", 2)
            if first_task:
                tasks.append(first_task)
                
                # Fetch more receipts non-blocking (up to a batch of 50) — single roundtrip
                from app.services.redis_queue import get_redis_client
                r = get_redis_client()
                batch = r.lpop("crm_receipt_queue", count=49)
                if batch:
                    for val in batch:
                        try:
                            tasks.append(json.loads(val))
                        except Exception as parse_err:
                            logger.error(f"Failed to parse popped receipt JSON: {parse_err}")

            if tasks:
                logger.info(f"Processing batch of {len(tasks)} delivery receipts...")
                async with pool.acquire() as conn:
                    for task in tasks:
                        # Process each task in its own transaction (savepoint) so one error doesn't abort the batch
                        try:
                            async with conn.transaction():
                                comm_id_str = task.get("communication_id")
                                event_type = task.get("event_type")
                                idempotency_key = task.get("idempotency_key")
                                event_data = task.get("event_data") or {}

                                if not comm_id_str or not event_type or not idempotency_key:
                                    logger.warning(f"Invalid receipt task skipped: {task}")
                                    continue

                                comm_id = UUID(comm_id_str)

                                # 1. Try to insert delivery event (Idempotent check via ON CONFLICT DO NOTHING)
                                event_id = await conn.fetchval(
                                    """
                                    INSERT INTO delivery_events (communication_id, event_type, event_data, idempotency_key)
                                    VALUES ($1, $2, $3::jsonb, $4)
                                    ON CONFLICT (idempotency_key) DO NOTHING
                                    RETURNING id
                                    """,
                                    comm_id, event_type, json.dumps(event_data), idempotency_key
                                )

                                if not event_id:
                                    logger.info(f"Duplicate receipt skipped: key={idempotency_key}")
                                    continue

                                # 2. Fetch communication details
                                comm = await conn.fetchrow(
                                    "SELECT campaign_id, customer_id, channel, status FROM communications WHERE id = $1",
                                    comm_id
                                )
                                if not comm:
                                    logger.warning(f"Communication {comm_id} not found for receipt")
                                    continue

                                campaign_id = comm["campaign_id"]
                                customer_id = comm["customer_id"]
                                current_status = comm["status"]

                                # 3. Status transition rules
                                STATUS_ORDER = {
                                    "pending": 0,
                                    "sent": 1,
                                    "delivered": 2,
                                    "opened": 3,
                                    "clicked": 4,
                                    "converted": 5
                                }

                                if event_type == "failed":
                                    await conn.execute(
                                        """
                                        UPDATE communications
                                        SET status = 'failed', failed_at = NOW(), failure_reason = $1
                                        WHERE id = $2
                                        """,
                                        event_data.get("failure_reason", "unknown"), comm_id
                                    )
                                    await conn.execute(
                                        "UPDATE campaigns SET total_failed = total_failed + 1 WHERE id = $1",
                                        campaign_id
                                    )
                                    continue

                                # Skip if out-of-order or duplicate status update
                                if STATUS_ORDER.get(event_type, -1) <= STATUS_ORDER.get(current_status, -1):
                                    logger.warning(
                                        f"Out-of-order event skipped: comm={comm_id}, current={current_status}, received={event_type}"
                                    )
                                    continue

                                # Process state advance
                                if event_type == "converted":
                                    revenue = event_data.get("order_value")
                                    if revenue is not None:
                                        revenue = float(revenue)
                                    else:
                                        revenue = 0.0

                                    items_count = int(event_data.get("items_count", 1))
                                    cat = event_data.get("category")
                                    prod = event_data.get("product_name")

                                    # Retrieve product names and prices from the brand_profile database table
                                    brand_profile_row = await conn.fetchrow("SELECT data FROM brand_profile ORDER BY id DESC LIMIT 1")
                                    brand_catalog = []
                                    if brand_profile_row:
                                        bp_data = brand_profile_row["data"]
                                        if isinstance(bp_data, str):
                                            bp_data = json.loads(bp_data)
                                        brand_catalog = bp_data.get("product_catalog", [])

                                    if brand_catalog:
                                        matched_product = None
                                        if prod:
                                            # Match by product name if possible
                                            for p in brand_catalog:
                                                if p.get("name", "").lower() == prod.lower():
                                                    matched_product = p
                                                    break
                                        if not matched_product and revenue > 0:
                                            # Match by closest price
                                            target_price = revenue / max(items_count, 1)
                                            closest_diff = None
                                            for p in brand_catalog:
                                                try:
                                                    price = float(p.get("price") or 0)
                                                    diff = abs(price - target_price)
                                                    if closest_diff is None or diff < closest_diff:
                                                        closest_diff = diff
                                                        matched_product = p
                                                except:
                                                    pass
                                        if not matched_product:
                                            matched_product = brand_catalog[0]
                                        
                                        if matched_product:
                                            prod = matched_product.get("name", prod)
                                            cat = matched_product.get("category", cat)
                                            if revenue == 0.0:
                                                try:
                                                    revenue = float(matched_product.get("price", 0)) * items_count
                                                except:
                                                    pass

                                    if not prod:
                                        prod = "Campaign Product"
                                    if not cat:
                                        cat = "Campaign Sale"

                                    await conn.execute(
                                        """
                                        UPDATE communications
                                        SET status = 'converted', converted_at = NOW(), attributed_revenue = $1
                                        WHERE id = $2
                                        """,
                                        revenue, comm_id
                                    )

                                    await conn.execute(
                                        """
                                        UPDATE campaigns
                                        SET total_conversions = total_conversions + 1,
                                            total_attributed_revenue = total_attributed_revenue + COALESCE($2, 0.00)
                                        WHERE id = $1
                                        """,
                                        campaign_id, revenue
                                    )

                                    await conn.execute(
                                        """
                                        INSERT INTO orders (customer_id, order_date, total_amount, items_count, status, category, product_name)
                                        VALUES ($1, NOW(), $2, $3, 'completed', $4, $5)
                                        """,
                                        customer_id, revenue, items_count, cat, prod
                                    )

                                    # Update customer statistics
                                    await conn.execute(
                                        """
                                        UPDATE customers
                                        SET total_spent = total_spent + $1,
                                            total_orders = total_orders + 1,
                                            last_order_at = NOW()
                                        WHERE id = $2
                                        """,
                                        revenue, customer_id
                                    )
                                else:
                                    timestamp_field = f"{event_type}_at"
                                    await conn.execute(
                                        f"UPDATE communications SET status = $1, {timestamp_field} = NOW() WHERE id = $2",
                                        event_type, comm_id
                                    )

                                    counter_map = {
                                        "sent": "total_sent",
                                        "delivered": "total_delivered",
                                        "opened": "total_opened",
                                        "clicked": "total_clicked",
                                    }
                                    counter_field = counter_map.get(event_type)
                                    if counter_field:
                                        await conn.execute(
                                            f"UPDATE campaigns SET {counter_field} = {counter_field} + 1 WHERE id = $1",
                                            campaign_id
                                        )

                        except Exception as task_err:
                            logger.error(f"Error processing receipt task {task}: {task_err}", exc_info=True)

            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("Receipt Worker shutting down.")
            break
        except Exception as e:
            logger.error(f"Error in Receipt Worker loop: {e}", exc_info=True)
            await asyncio.sleep(2)
