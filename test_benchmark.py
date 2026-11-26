from models import SessionLocal, Item, Customer, Invoice, Payment
from sqlalchemy import func
from engine import (
    get_stock_base, record_purchase, record_production_run,
    create_order, approve_invoice_and_dispatch, record_payment
)

db = SessionLocal()

flour = db.query(Item).filter_by(name="Flour").first()
oil = db.query(Item).filter_by(name="Cooking Oil").first()
spice = db.query(Item).filter_by(name="Salt & Spice Mix").first()
pouch = db.query(Item).filter_by(name="200g Pouch").first()
murukku = db.query(Item).filter_by(name="Murukku 200g").first()
ret_a = db.query(Customer).filter_by(name="Retailer A").first()
dist_b = db.query(Customer).filter_by(name="Distributor B").first()

# Step 1: Purchase 60 kg flour @ ₹45/kg
record_purchase(db, "Sri Murugan Agro", flour.id, 60, 45.0)

# Step 2, 3 & 8: Production run
run = record_production_run(
    db, murukku.id,
    actual_raw_issued_display={flour.id: 40.0, oil.id: 10.5, spice.id: 1.2},
    actual_good_packets=188, damaged_pouches=6, cartons_used=9,
    labour_rupees=1200.0, overhead_rupees=600.0
)

# Step 4 & 5: Salesman A -> Retailer A (150 pkts) -> Invoice & Dispatch
ord_a = create_order(db, "salesman_a", ret_a.id, murukku.id, 150)
res_a = approve_invoice_and_dispatch(db, ord_a.id)
inv_a = res_a["invoice"]

# Step 6: Salesman B -> Distributor B (120 pkts) -> Shortage Check
ord_b = create_order(db, "salesman_b", dist_b.id, murukku.id, 120)
res_b = approve_invoice_and_dispatch(db, ord_b.id)

# Step 7: Payment ₹4,000 from Retailer A
record_payment(db, inv_a.id, 4000.0)
paid_paise = db.query(func.sum(Payment.amount_paise)).filter_by(invoice_id=inv_a.id).scalar() or 0

print("\n=== NIT TRICHY BENCHMARK VERIFICATION ===")
print(f"1. Flour closing:      {get_stock_base(db, flour.id)/1000} kg (Expected: 120 kg)")
print(f"2. Oil closing:        {get_stock_base(db, oil.id)/1000} L (Expected: 19.5 L)")
print(f"3. Pouches closing:    {get_stock_base(db, pouch.id)} pcs (Expected: 306)")
print(f"4. Finished after A:   {get_stock_base(db, murukku.id)} pkts (Expected: 88)")
print(f"5. Variance Alerts:    {run.variance_notes}")
print(f"6. Retailer A Invoice: ₹{inv_a.taxable_paise/100:.2f} + CGST ₹{inv_a.cgst_paise/100:.2f} + SGST ₹{inv_a.sgst_paise/100:.2f} = ₹{inv_a.grand_total_paise/100:.2f}")
print(f"7. Retailer A Due:     ₹{(inv_a.grand_total_paise - paid_paise)/100:.2f} (Expected: ₹3875.00)")
print(f"8. Distributor B:      {res_b} (Expected: Shortage of 32)")
print(f"9. Cost per packet:    ₹{run.cost_per_packet_paise/100:.2f} (Weighted Avg Flour ₹43.13/kg + Direct Labour/Power)")