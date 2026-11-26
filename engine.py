from sqlalchemy.orm import Session
from sqlalchemy import func
from models import (
    Item, RecipeBOM, StockLedger, Purchase, ProductionRun,
    Customer, Order, Invoice, Payment, AuditLog
)

FACTORY_STATE = "Tamil Nadu"
VARIANCE_TOLERANCE_PCT = 3.0  # Flag anything > 3% variance

def get_stock_base(db: Session, item_id: int) -> int:
    """Returns exact current balance in base units (g, ml, pcs) from StockLedger."""
    return db.query(func.sum(StockLedger.qty_delta_base)).filter(
        StockLedger.item_id == item_id
    ).scalar() or 0

def get_weighted_avg_cost_paise(db: Session, item_id: int) -> int:
    """
    Computes Weighted Average Cost per display unit (e.g., per kg, per L, per pc)
    from all OPENING and PURCHASE ledger entries.
    """
    item = db.query(Item).get(item_id)
    entries = db.query(StockLedger).filter(
        StockLedger.item_id == item_id,
        StockLedger.movement_type.in_(["OPENING", "PURCHASE"])
    ).all()

    total_display_qty = 0.0
    total_value_paise = 0.0
    for e in entries:
        disp_qty = e.qty_delta_base / item.conversion_factor
        total_display_qty += disp_qty
        total_value_paise += disp_qty * e.unit_cost_paise

    if total_display_qty == 0:
        return 0
    return round(total_value_paise / total_display_qty)

def record_purchase(db: Session, supplier: str, item_id: int, qty_display: float, rate_rupees: float, user: str = "supervisor"):
    item = db.query(Item).get(item_id)
    qty_base = round(qty_display * item.conversion_factor)
    rate_paise = round(rate_rupees * 100)
    total_paise = round(qty_display * rate_paise)

    purchase = Purchase(
        supplier_name=supplier,
        item_id=item_id,
        qty_base=qty_base,
        rate_per_display_unit_paise=rate_paise,
        total_paise=total_paise
    )
    db.add(purchase)
    db.flush()

    db.add(StockLedger(
        item_id=item_id,
        movement_type="PURCHASE",
        qty_delta_base=qty_base,
        unit_cost_paise=rate_paise,
        ref_type="PURCHASE",
        ref_id=purchase.id
    ))
    db.add(AuditLog(username=user, action="PURCHASE", details=f"Bought {qty_display} {item.display_unit} {item.name} @ ₹{rate_rupees}"))
    db.commit()
    return purchase

def record_production_run(
    db: Session,
    finished_item_id: int,
    actual_raw_issued_display: dict,  # {item_id: qty_in_display_unit}
    actual_good_packets: int,
    damaged_pouches: int,
    cartons_used: int,
    labour_rupees: float,
    overhead_rupees: float,
    batches: float = 1.0,
    user: str = "supervisor"
):
    bom_rows = db.query(RecipeBOM).filter(RecipeBOM.finished_item_id == finished_item_id).all()
    expected_packets = round(bom_rows[0].expected_yield_pcs * batches)

    yield_var_pct = round(((actual_good_packets - expected_packets) / expected_packets) * 100, 2)
    yield_flagged = abs(yield_var_pct) > VARIANCE_TOLERANCE_PCT

    total_material_cost_paise = 0
    variance_alerts = []
    if yield_flagged:
        variance_alerts.append(f"Yield variance {yield_var_pct:+.1f}% ({actual_good_packets} vs {expected_packets} expected)")

    # Calculate weighted average rates BEFORE deducting stock
    rates_paise = {b.ingredient_item_id: get_weighted_avg_cost_paise(db, b.ingredient_item_id) for b in bom_rows}

    run = ProductionRun(
        finished_item_id=finished_item_id,
        batches=batches,
        expected_packets=expected_packets,
        actual_good_packets=actual_good_packets,
        damaged_pouches=damaged_pouches,
        cartons_used=cartons_used,
        yield_variance_pct=yield_var_pct,
        yield_flagged=yield_flagged,
        labour_cost_paise=round(labour_rupees * 100),
        overhead_cost_paise=round(overhead_rupees * 100),
    )
    db.add(run)
    db.flush()

    # Deduct Raw & Packaging Materials in StockLedger
    for b in bom_rows:
        ing = db.query(Item).get(b.ingredient_item_id)
        std_disp = (b.std_qty_base / ing.conversion_factor) * batches
        rate_p = rates_paise[ing.id]

        if ing.category == "RAW":
            used_disp = actual_raw_issued_display.get(ing.id, std_disp)
            used_base = round(used_disp * ing.conversion_factor)
            cons_var_pct = round(((used_disp - std_disp) / std_disp) * 100, 2)
            if abs(cons_var_pct) > VARIANCE_TOLERANCE_PCT:
                variance_alerts.append(f"{ing.name} variance {cons_var_pct:+.1f}% ({used_disp} vs {std_disp} {ing.display_unit})")

            total_material_cost_paise += round(used_disp * rate_p)
            db.add(StockLedger(
                item_id=ing.id, movement_type="PROD_ISSUE", qty_delta_base=-used_base,
                unit_cost_paise=rate_p, ref_type="PRODUCTION", ref_id=run.id
            ))

        elif "Pouch" in ing.name:
            # Good packets + damaged pouches consumed
            total_material_cost_paise += round((actual_good_packets + damaged_pouches) * rate_p)
            db.add(StockLedger(
                item_id=ing.id, movement_type="PROD_ISSUE", qty_delta_base=-actual_good_packets,
                unit_cost_paise=rate_p, ref_type="PRODUCTION", ref_id=run.id
            ))
            if damaged_pouches > 0:
                db.add(StockLedger(
                    item_id=ing.id, movement_type="WASTAGE", qty_delta_base=-damaged_pouches,
                    unit_cost_paise=rate_p, ref_type="PRODUCTION", ref_id=run.id
                ))

        elif "Carton" in ing.name:
            total_material_cost_paise += round(cartons_used * rate_p)
            db.add(StockLedger(
                item_id=ing.id, movement_type="PROD_ISSUE", qty_delta_base=-cartons_used,
                unit_cost_paise=rate_p, ref_type="PRODUCTION", ref_id=run.id
            ))

    total_run_cost_paise = total_material_cost_paise + run.labour_cost_paise + run.overhead_cost_paise
    cost_per_pkt_paise = round(total_run_cost_paise / actual_good_packets) if actual_good_packets > 0 else 0

    run.total_run_cost_paise = total_run_cost_paise
    run.cost_per_packet_paise = cost_per_pkt_paise
    run.variance_notes = " | ".join(variance_alerts) if variance_alerts else "Within 3% tolerance"

    # Add Finished Goods to StockLedger
    db.add(StockLedger(
        item_id=finished_item_id, movement_type="PROD_OUTPUT", qty_delta_base=actual_good_packets,
        unit_cost_paise=cost_per_pkt_paise, ref_type="PRODUCTION", ref_id=run.id
    ))
    db.add(AuditLog(username=user, action="PRODUCTION_RUN", details=f"Run #{run.id}: Produced {actual_good_packets} pkts. Alerts: {run.variance_notes}"))
    db.commit()
    return run

def create_order(db: Session, salesman: str, customer_id: int, item_id: int, qty_packets: int):
    item = db.query(Item).get(item_id)
    order = Order(
        salesman_name=salesman,
        customer_id=customer_id,
        item_id=item_id,
        qty_packets=qty_packets,
        unit_price_paise=item.selling_price_paise,
        status="SUBMITTED"
    )
    db.add(order)
    db.add(AuditLog(username=salesman, action="ORDER_CREATED", details=f"Order for {qty_packets} pkts"))
    db.commit()
    return order

def approve_invoice_and_dispatch(db: Session, order_id: int, user: str = "admin"):
    order = db.query(Order).get(order_id)
    available = get_stock_base(db, order.item_id)

    if available < order.qty_packets:
        shortage = order.qty_packets - available
        order.status = "SHORTAGE_HOLD"
        db.commit()
        return {"ok": False, "shortage": shortage, "available": available}

    customer = db.query(Customer).get(order.customer_id)
    item = db.query(Item).get(order.item_id)

    taxable_paise = order.qty_packets * order.unit_price_paise
    total_gst_paise = round(taxable_paise * (item.gst_rate / 100.0))

    if customer.state == FACTORY_STATE:
        cgst_paise = total_gst_paise // 2
        sgst_paise = total_gst_paise - cgst_paise
        igst_paise = 0
    else:
        cgst_paise = 0
        sgst_paise = 0
        igst_paise = total_gst_paise

    grand_total_paise = taxable_paise + cgst_paise + sgst_paise + igst_paise
    inv_count = db.query(Invoice).count() + 1

    invoice = Invoice(
        invoice_no=f"INV/26-27/{inv_count:04d}",
        order_id=order.id,
        customer_id=customer.id,
        taxable_paise=taxable_paise,
        cgst_paise=cgst_paise,
        sgst_paise=sgst_paise,
        igst_paise=igst_paise,
        grand_total_paise=grand_total_paise,
        dispatched=True
    )
    db.add(invoice)
    db.flush()

    order.status = "DISPATCHED"
    db.add(StockLedger(
        item_id=item.id, movement_type="DISPATCH", qty_delta_base=-order.qty_packets,
        unit_cost_paise=order.unit_price_paise, ref_type="INVOICE", ref_id=invoice.id
    ))
    db.add(AuditLog(username=user, action="INVOICE_DISPATCH", details=f"{invoice.invoice_no} dispatched ({order.qty_packets} pkts)"))
    db.commit()
    return {"ok": True, "invoice": invoice}

def record_payment(db: Session, invoice_id: int, amount_rupees: float, user: str = "admin"):
    inv = db.query(Invoice).get(invoice_id)
    amt_paise = round(amount_rupees * 100)
    pay = Payment(invoice_id=inv.id, customer_id=inv.customer_id, amount_paise=amt_paise)
    db.add(pay)
    db.add(AuditLog(username=user, action="PAYMENT_RECEIVED", details=f"₹{amount_rupees} against {inv.invoice_no}"))
    db.commit()
    return pay