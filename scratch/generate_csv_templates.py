import csv
import os
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from faker import Faker

fake = Faker("en_IN")

# ── Weighted Indian Cities ──
CITIES = {
    "Mumbai": 20, "Delhi": 18, "Bangalore": 15, "Hyderabad": 10,
    "Chennai": 8, "Pune": 8, "Kolkata": 6, "Ahmedabad": 5,
    "Jaipur": 4, "Lucknow": 3, "Surat": 3,
}

# ── Clothing Brand Catalog ──
PRODUCTS = {
    "Apparel": [
        ("Organic Cotton Crewneck", 1850.00),
        ("Sustainable Denim Jacket", 4200.00),
        ("Linen Summer Shirt", 2100.00),
        ("Chino Trousers", 2500.00)
    ],
    "Knitwear": [
        ("Merino Wool Knit Sweater", 3500.00),
        ("Cashmere Cardigan", 6500.00)
    ],
    "Footwear": [
        ("Minimalist Canvas Sneakers", 2400.00),
        ("Eco Slip-on Loafers", 2800.00)
    ],
    "Outerwear": [
        ("Recycled Polyester Windbreaker", 2900.00),
        ("Heavyweight Parka", 5800.00)
    ]
}

CATEGORIES = list(PRODUCTS.keys())

def _weighted_city() -> str:
    cities = list(CITIES.keys())
    weights = list(CITIES.values())
    return random.choices(cities, weights=weights, k=1)[0]

def main():
    os.makedirs("ingestion_templates", exist_ok=True)
    
    print("Generating 1500 realistic customer profiles...")
    
    # Archetype Distribution (1500 total)
    # VIP (15% = 225), Active (35% = 525), Lapsed (25% = 375), New (25% = 375)
    archetypes = (
        ["vip"] * 225 +
        ["active"] * 525 +
        ["lapsed"] * 375 +
        ["new"] * 375
    )
    random.shuffle(archetypes)
    
    customers = []
    orders = []
    
    now = datetime.now(timezone.utc)
    
    for i, archetype in enumerate(archetypes, start=1):
        name = fake.name()
        # Clean name for emails
        email_name = name.lower().replace(" ", ".").replace("'", "").replace("\"", "")
        email = f"{email_name}@{fake.free_email_domain()}"
        phone = f"+91{fake.msisdn()[4:]}"
        ext_id = f"cust_{uuid4().hex[:12]}"
        city = _weighted_city()
        
        tags = []
        if archetype == "vip":
            tags = ["vip", "high_value", random.choice(["fashion", "premium"])]
        elif archetype == "active":
            tags = ["regular", random.choice(["fashion", "grocery"])]
        elif archetype == "lapsed":
            tags = ["lapsed", "budget"]
        elif archetype == "new":
            tags = ["new"]
            
        tags.append(random.choice(["whatsapp_opted", "email_opted", "sms_opted"]))
        tags = list(set(tags))
        
        # Customer row
        customers.append({
            "name": name,
            "city": city,
            "tags": ",".join(tags),
            "external_id": ext_id,
            "email": email,
            "phone": phone
        })
        
        # Generate orders matching archetype
        num_orders = 0
        if archetype == "vip":
            num_orders = random.randint(10, 30)
            max_days = 180
        elif archetype == "active":
            num_orders = random.randint(3, 10)
            max_days = 120
        elif archetype == "lapsed":
            num_orders = random.randint(1, 5)
            max_days = 365
        elif archetype == "new":
            num_orders = random.randint(0, 2)
            max_days = 14
            
        for _ in range(num_orders):
            days_ago = random.randint(60 if archetype == "lapsed" else 1, max_days)
            order_date = now - timedelta(days=days_ago)
            
            # Select random item from catalog
            cat = random.choice(CATEGORIES)
            prod_info = random.choice(PRODUCTS[cat])
            product_name = prod_info[0]
            price = prod_info[1]
            
            items_count = random.randint(1, 4)
            total_amount = price * items_count
            
            orders.append({
                "customer_external_id": ext_id,
                "total_amount": f"{total_amount:.2f}",
                "order_date": order_date.strftime("%Y-%m-%d %H:%M:%S"),
                "items_count": items_count,
                "category": cat,
                "product_name": product_name
            })
            
    # Write customers.csv
    customers_file = "ingestion_templates/customers.csv"
    with open(customers_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "city", "tags", "external_id", "email", "phone"])
        writer.writeheader()
        writer.writerows(customers)
        
    # Write orders.csv
    orders_file = "ingestion_templates/orders.csv"
    with open(orders_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["customer_external_id", "total_amount", "order_date", "items_count", "category", "product_name"])
        writer.writeheader()
        writer.writerows(orders)
        
    print(f"[OK] Generated {len(customers)} customers in {customers_file}")
    print(f"[OK] Generated {len(orders)} orders in {orders_file}")

if __name__ == "__main__":
    main()
