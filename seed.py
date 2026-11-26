from sqlalchemy import func
from models import SessionLocal, init_db, User, Item, RecipeBOM, StockLedger, Customer

def seed_database():
    # 1. Create the tables in factory.db
    init_db()
    db = SessionLocal()

    # Prevent duplicate seeding if run twice
    if db.query(Item).count() > 0:
        print("Database already seeded! Delete factory.db first if you want a fresh reset.")
        return

    print("Seeding users, items, BOM, opening stock, and customers...")

    # 2. Users (Roles)
    users = [
        User(username="salesman_a", role="salesman"),
        User(username="salesman_b", role="salesman"),
        User(username="admin", role="admin"),
        User(username="supervisor", role="production"),
        User(username="auditor", role="auditor"),
        User(username="owner", role="owner"),
    ]
    db.add_all(users)

    # 3. Items (Raw Materials, Packaging, Finished Goods)
    # Note: Money is stored in PAISE (₹42 = 4200 paise)
    flour = Item(name="Flour", category="RAW", base_unit="g", display_unit="kg", conversion_factor=1000)
    oil = Item(name="Cooking Oil", category="RAW", base_unit="ml", display_unit="L", conversion_factor=1000)
    spice = Item(name="Salt & Spice Mix", category="RAW", base_unit="g", display_unit="kg", conversion_factor=1000)
    pouch = Item(name="200g Pouch", category="PACKAGING", base_unit="pcs", display_unit="pcs", conversion_factor=1)
    carton = Item(name="Carton (20 pkts)", category="PACKAGING", base_unit="pcs", display_unit="pcs", conversion_factor=1)
    
    murukku_200g = Item(
        name="Murukku 200g",
        category="FINISHED",
        base_unit="pcs",
        display_unit="packets",
        conversion_factor=1,
        selling_price_paise=5000,  # ₹50.00
        hsn_code="210690",
        gst_rate=5.0
    )

    db.add_all([flour, oil, spice, pouch, carton, murukku_200g])
    db.commit()  # Commit so each item gets its ID

    # 4. Bill of Materials (BOM) for 1 Batch of Murukku 200g = 200 packets expected
    bom_entries = [
        RecipeBOM(finished_item_id=murukku_200g.id, ingredient_item_id=flour.id, std_qty_base=40000, expected_yield_pcs=200),  # 40 kg
        RecipeBOM(finished_item_id=murukku_200g.id, ingredient_item_id=oil.id, std_qty_base=10000, expected_yield_pcs=200),    # 10 L
        RecipeBOM(finished_item_id=murukku_200g.id, ingredient_item_id=spice.id, std_qty_base=1200, expected_yield_pcs=200),   # 1.2 kg
        RecipeBOM(finished_item_id=murukku_200g.id, ingredient_item_id=pouch.id, std_qty_base=200, expected_yield_pcs=200),    # 200 pcs
        RecipeBOM(finished_item_id=murukku_200g.id, ingredient_item_id=carton.id, std_qty_base=10, expected_yield_pcs=200),    # 10 pcs
    ]
    db.add_all(bom_entries)

    # 5. Opening Stock Balances (Recorded as OPENING entries in StockLedger!)
    opening_stock = [
        StockLedger(item_id=flour.id, movement_type="OPENING", qty_delta_base=100000, unit_cost_paise=4200, ref_type="SEED", ref_id=1),      # 100 kg @ ₹42
        StockLedger(item_id=oil.id, movement_type="OPENING", qty_delta_base=30000, unit_cost_paise=14000, ref_type="SEED", ref_id=1),       # 30 L @ ₹140
        StockLedger(item_id=spice.id, movement_type="OPENING", qty_delta_base=5000, unit_cost_paise=20000, ref_type="SEED", ref_id=1),      # 5 kg @ ₹200
        StockLedger(item_id=pouch.id, movement_type="OPENING", qty_delta_base=500, unit_cost_paise=250, ref_type="SEED", ref_id=1),         # 500 pcs @ ₹2.50
        StockLedger(item_id=carton.id, movement_type="OPENING", qty_delta_base=30, unit_cost_paise=1500, ref_type="SEED", ref_id=1),        # 30 pcs @ ₹15
        StockLedger(item_id=murukku_200g.id, movement_type="OPENING", qty_delta_base=50, unit_cost_paise=3000, ref_type="SEED", ref_id=1),  # 50 packets
    ]
    db.add_all(opening_stock)

    # 6. Customers (Tamil Nadu vs Karnataka for GST testing)
    customers = [
        Customer(name="Retailer A", state="Tamil Nadu", gstin="33AABCR1234A1Z5"),
        Customer(name="Distributor B", state="Karnataka", gstin="29AABCD5678B1Z9"),
    ]
    db.add_all(customers)
    db.commit()

    # 7. Verify by querying SUM(qty_delta_base) from StockLedger
    print("\n--- OPENING STOCK LEDGER VERIFICATION ---")
    for item in db.query(Item).all():
        total_base = db.query(func.sum(StockLedger.qty_delta_base)).filter(StockLedger.item_id == item.id).scalar() or 0
        display_qty = total_base / item.conversion_factor
        print(f"• {item.name}: {display_qty} {item.display_unit}")

    db.close()
    print("\nSuccess! 'factory.db' created and ready.")

if __name__ == "__main__":
    seed_database()