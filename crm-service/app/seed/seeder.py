"""
Seed Data Generator — Creates realistic demo data for the CRM.

Generates archetype-based customers with Indian locale:
  - VIP regulars (15%): High spend, frequent orders, recent activity
  - Active customers (35%): Moderate engagement
  - Lapsed customers (25%): Haven't ordered in 60+ days
  - New customers (25%): Joined recently, few or no orders

This creates compelling demo data where segmentation queries
actually return meaningful, differentiated results.

Total: 1500 customers, ~5000 orders
"""

import random
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from faker import Faker

logger = logging.getLogger(__name__)

fake = Faker("en_IN")

# ── Indian Cities (weighted for realistic distribution) ──
CITIES = {
    "Mumbai": 20, "Delhi": 18, "Bangalore": 15, "Hyderabad": 10,
    "Chennai": 8, "Pune": 8, "Kolkata": 6, "Ahmedabad": 5,
    "Jaipur": 4, "Lucknow": 3, "Surat": 3,
}

# ── Customer Tags ──
TAGS_POOL = [
    "vip", "regular", "new", "lapsed", "high_value", "budget",
    "electronics", "fashion", "grocery", "fitness",
    "whatsapp_opted", "email_opted", "sms_opted",
]


def _weighted_city() -> str:
    """Pick a city weighted by population distribution."""
    cities = list(CITIES.keys())
    weights = list(CITIES.values())
    return random.choices(cities, weights=weights, k=1)[0]


def _generate_customer(archetype: str) -> dict:
    """Generate a customer profile based on archetype."""
    name = fake.name()
    phone = f"+91{fake.msisdn()[4:]}"

    tags = []
    if archetype == "vip":
        tags = ["vip", "high_value", random.choice(["electronics", "fashion"])]
    elif archetype == "active":
        tags = ["regular", random.choice(["whatsapp_opted", "email_opted"])]
    elif archetype == "lapsed":
        tags = ["lapsed", random.choice(["budget", "regular"])]
    elif archetype == "new":
        tags = ["new"]
    tags.append(random.choice(["whatsapp_opted", "email_opted", "sms_opted"]))
    tags = list(set(tags))  # Deduplicate

    return {
        "external_id": f"cust_{uuid4().hex[:12]}",
        "name": name,
        "email": f"{name.lower().replace(' ', '.')}@{fake.free_email_domain()}",
        "phone": phone,
        "whatsapp_id": phone,
        "city": _weighted_city(),
        "tags": tags,
    }


def _generate_orders(
    customer_id, archetype: str
) -> list[dict]:
    """Generate orders for a customer based on archetype."""
    now = datetime.now(timezone.utc)
    orders = []

    if archetype == "vip":
        # VIPs: 10-30 orders, recent, high value
        num_orders = random.randint(10, 30)
        for _ in range(num_orders):
            days_ago = random.randint(1, 180)
            orders.append({
                "customer_id": customer_id,
                "order_date": now - timedelta(days=days_ago),
                "total_amount": round(random.uniform(2000, 15000), 2),
                "items_count": random.randint(1, 8),
                "status": "completed",
            })

    elif archetype == "active":
        # Active: 3-10 orders, moderate value
        num_orders = random.randint(3, 10)
        for _ in range(num_orders):
            days_ago = random.randint(1, 120)
            orders.append({
                "customer_id": customer_id,
                "order_date": now - timedelta(days=days_ago),
                "total_amount": round(random.uniform(500, 5000), 2),
                "items_count": random.randint(1, 5),
                "status": "completed",
            })

    elif archetype == "lapsed":
        # Lapsed: 1-5 orders, all older than 60 days
        num_orders = random.randint(1, 5)
        for _ in range(num_orders):
            days_ago = random.randint(60, 365)
            orders.append({
                "customer_id": customer_id,
                "order_date": now - timedelta(days=days_ago),
                "total_amount": round(random.uniform(200, 3000), 2),
                "items_count": random.randint(1, 3),
                "status": "completed",
            })

    elif archetype == "new":
        # New: 0-2 orders, very recent
        num_orders = random.randint(0, 2)
        for _ in range(num_orders):
            days_ago = random.randint(1, 14)
            orders.append({
                "customer_id": customer_id,
                "order_date": now - timedelta(days=days_ago),
                "total_amount": round(random.uniform(300, 2000), 2),
                "items_count": random.randint(1, 3),
                "status": "completed",
            })

    return orders


async def seed_demo_data(pool) -> dict:
    """
    Generate and insert demo data.

    Returns:
        Summary dict with counts of generated data.
    """
    from app.repositories import customer_repo, order_repo

    logger.info("Seeding demo data...")

    # ── Archetype Distribution ──
    archetypes = (
        ["vip"] * 225 +       # 15% of 1500
        ["active"] * 525 +    # 35%
        ["lapsed"] * 375 +    # 25%
        ["new"] * 375         # 25%
    )
    random.shuffle(archetypes)

    total_customers = 0
    total_orders = 0

    for archetype in archetypes:
        # Generate customer
        customer_data = _generate_customer(archetype)
        customer_id = await customer_repo.insert_customer(pool, customer_data)

        if customer_id is None:
            continue
        total_customers += 1

        # Generate orders
        orders = _generate_orders(customer_id, archetype)
        for order in orders:
            try:
                await order_repo.insert_order(pool, order)
                total_orders += 1
            except Exception as e:
                logger.warning(f"Failed to insert seed order: {e}")

        # Update customer aggregates
        await customer_repo.update_customer_aggregates(pool, customer_id)

    summary = {
        "customers": total_customers,
        "orders": total_orders,
        "archetypes": {
            "vip": 225,
            "active": 525,
            "lapsed": 375,
            "new": 375,
        },
    }
    logger.info(f"✓ Seeded {total_customers} customers with {total_orders} orders")
    return summary
