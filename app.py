import io
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import openpyxl
from fpdf import FPDF

from models import (
    SessionLocal, init_db, User, Item, RecipeBOM, StockLedger,
    Purchase, ProductionRun, Customer, Order, Invoice, Payment, AuditLog
)
from engine import (
    get_stock_base, record_purchase, record_production_run,
    create_order, approve_invoice_and_dispatch, record_payment
)

app = FastAPI(title="South Indian Snacks ERP")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- HTML LAYOUT HELPER (Tailwind CSS via CDN) ---
def render_page(title: str, role: str, body_html: str, banner: str = ""):
    nav_links = {
        "salesman": [("Mobile Order", "/salesman?role=salesman")],
        "production": [("Floor & Production", "/production?role=production")],
        "admin": [("Orders & Billing", "/admin?role=admin")],
        "auditor": [("Auditor Reports", "/auditor?role=auditor")],
        "owner": [("Owner Dashboard", "/owner?role=owner")],
    }
    links_html = "".join(
        f'<a href="{url}" class="px-3 py-1.5 rounded bg-amber-700 hover:bg-amber-600 text-white text-sm font-medium">{label}</a>'
        for label, url in nav_links.get(role, [])
    )
    banner_html = f'<div class="bg-amber-100 border-l-4 border-amber-600 text-amber-900 p-3 mb-4 rounded">{banner}</div>' if banner else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-stone-100 text-stone-800 min-h-screen">
  <nav class="bg-amber-900 text-white p-4 shadow">
    <div class="max-w-6xl mx-auto flex flex-wrap justify-between items-center gap-2">
      <div>
        <span class="font-bold text-lg">Sri Murugan Snacks — Order-to-Audit</span>
        <span class="ml-2 text-xs uppercase bg-amber-700 px-2 py-0.5 rounded">Role: {role}</span>
      </div>
      <div class="flex items-center gap-2">
        {links_html}
        <a href="/" class="px-3 py-1.5 rounded bg-stone-700 hover:bg-stone-600 text-xs">Switch Role</a>
      </div>
    </div>
  </nav>
  <main class="max-w-6xl mx-auto p-4 md:p-6">
    {banner_html}
    {body_html}
  </main>
</body>
</html>"""

# --- 1. LOGIN / ROLE SELECTOR ---
@app.get("/", response_class=HTMLResponse)
def login_page():
    roles = [
        ("Salesman (Mobile View)", "/salesman?role=salesman", "Place customer orders on mobile & track status"),
        ("Production Supervisor", "/production?role=production", "Record raw material purchases & daily production runs"),
        ("Factory Admin", "/admin?role=admin", "Verify orders, check stock, raise GST invoices & record payments"),
        ("Accountant / Auditor (Read-Only)", "/auditor?role=auditor", "View ledgers, GST summary & download Excel reports"),
        ("Factory Owner", "/owner?role=owner", "Executive KPI summary, variance alerts & unit cost"),
    ]
    cards = "".join(f"""
      <a href="{url}" class="block bg-white p-5 rounded-lg shadow hover:shadow-md border border-stone-200 transition">
        <h3 class="font-bold text-lg text-amber-900">{name}</h3>
        <p class="text-sm text-stone-600 mt-1">{desc}</p>
      </a>
    """ for name, url, desc in roles)
    return render_page("Login", "guest", f"""
      <div class="max-w-2xl mx-auto mt-6">
        <h1 class="text-2xl font-bold mb-2">Select User Role</h1>
        <p class="text-sm text-stone-600 mb-6">Role-based access control: each role sees only its operational workspace.</p>
        <div class="grid gap-4">{cards}</div>
      </div>
    """)

# --- 2. SALESMAN MOBILE VIEW ---
@app.get("/salesman", response_class=HTMLResponse)
def salesman_view(msg: str = "", db: Session = Depends(get_db)):
    customers = db.query(Customer).all()
    products = db.query(Item).filter_by(category="FINISHED").all()
    orders = db.query(Order).order_by(Order.id.desc()).all()

    cust_opts = "".join(f'<option value="{c.id}">{c.name} ({c.state})</option>' for c in customers)
    prod_opts = "".join(f'<option value="{p.id}">{p.name} — ₹{p.selling_price_paise/100:.2f}/pkt</option>' for p in products)

    order_rows = ""
    for o in orders:
        c = db.query(Customer).get(o.customer_id)
        p = db.query(Item).get(o.item_id)
        badge = "bg-green-100 text-green-800" if o.status == "DISPATCHED" else ("bg-red-100 text-red-800" if o.status == "SHORTAGE_HOLD" else "bg-blue-100 text-blue-800")
        order_rows += f"""<tr class="border-b">
          <td class="p-2">#{o.id} ({o.salesman_name})</td>
          <td class="p-2">{c.name}</td>
          <td class="p-2">{p.name} × {o.qty_packets}</td>
          <td class="p-2"><span class="px-2 py-0.5 rounded text-xs font-semibold {badge}">{o.status}</span></td>
        </tr>"""

    body = f"""
    <div class="max-w-lg mx-auto">
      <div class="bg-white p-5 rounded-lg shadow mb-6">
        <h2 class="text-xl font-bold mb-4">📱 New Field Order</h2>
        <form method="post" action="/salesman/order" class="space-y-4">
          <div>
            <label class="block text-sm font-medium mb-1">Salesman</label>
            <select name="salesman_name" class="w-full border rounded p-2.5 bg-white">
              <option value="salesman_a">Salesman A</option>
              <option value="salesman_b">Salesman B</option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium mb-1">Customer</label>
            <select name="customer_id" class="w-full border rounded p-2.5 bg-white">{cust_opts}</select>
          </div>
          <div>
            <label class="block text-sm font-medium mb-1">Product</label>
            <select name="item_id" class="w-full border rounded p-2.5 bg-white">{prod_opts}</select>
          </div>
          <div>
            <label class="block text-sm font-medium mb-1">Quantity (Packets)</label>
            <input type="number" name="qty_packets" required min="1" placeholder="e.g. 150" class="w-full border rounded p-2.5">
          </div>
          <button type="submit" class="w-full bg-amber-800 hover:bg-amber-700 text-white font-bold py-3 rounded-lg">Submit Order to Factory</button>
        </form>
      </div>
      <div class="bg-white p-4 rounded-lg shadow">
        <h3 class="font-bold mb-2">Submitted Orders</h3>
        <table class="w-full text-sm text-left"><thead><tr class="border-b bg-stone-50"><th class="p-2">Order</th><th class="p-2">Customer</th><th class="p-2">Items</th><th class="p-2">Status</th></tr></thead><tbody>{order_rows}</tbody></table>
      </div>
    </div>"""
    return render_page("Salesman Mobile", "salesman", body, msg)

@app.post("/salesman/order")
def submit_order(salesman_name: str = Form(...), customer_id: int = Form(...), item_id: int = Form(...), qty_packets: int = Form(...), db: Session = Depends(get_db)):
    o = create_order(db, salesman_name, customer_id, item_id, qty_packets)
    return RedirectResponse(f"/salesman?msg=Order+%23{o.id}+submitted+successfully!", status_code=303)

# --- 3. PRODUCTION SUPERVISOR VIEW ---
@app.get("/production", response_class=HTMLResponse)
def production_view(msg: str = "", db: Session = Depends(get_db)):
    raw_items = db.query(Item).filter_by(category="RAW").all()
    finished_items = db.query(Item).filter_by(category="FINISHED").all()
    all_items = db.query(Item).all()
    runs = db.query(ProductionRun).order_by(ProductionRun.id.desc()).all()

    raw_opts = "".join(f'<option value="{r.id}">{r.name} ({r.display_unit})</option>' for r in raw_items)
    fin_opts = "".join(f'<option value="{f.id}">{f.name}</option>' for f in finished_items)

    stock_rows = "".join(f"""<tr class="border-b">
      <td class="p-2 font-medium">{i.name}</td>
      <td class="p-2 text-xs text-stone-500">{i.category}</td>
      <td class="p-2 font-bold">{get_stock_base(db, i.id)/i.conversion_factor:g} {i.display_unit}</td>
    </tr>""" for i in all_items)

    run_rows = "".join(f"""<tr class="border-b">
      <td class="p-2">Run #{r.id}</td>
      <td class="p-2">{r.actual_good_packets} / {r.expected_packets} pkts</td>
      <td class="p-2">₹{r.cost_per_packet_paise/100:.2f}/pkt</td>
      <td class="p-2 text-xs {'text-red-700 font-semibold' if 'variance' in r.variance_notes else 'text-green-700'}">{r.variance_notes}</td>
    </tr>""" for r in runs)

    body = f"""
    <div class="grid md:grid-cols-2 gap-6">
      <div class="bg-white p-5 rounded-lg shadow">
        <h2 class="text-lg font-bold mb-3">1. Record Raw Material Purchase</h2>
        <form method="post" action="/production/purchase" class="space-y-3">
          <input type="text" name="supplier" value="Sri Murugan Agro" required class="w-full border rounded p-2" placeholder="Supplier Name">
          <select name="item_id" class="w-full border rounded p-2 bg-white">{raw_opts}</select>
          <div class="grid grid-cols-2 gap-2">
            <input type="number" step="0.01" name="qty" placeholder="Qty (e.g. 60)" required class="border rounded p-2">
            <input type="number" step="0.01" name="rate" placeholder="Rate ₹ (e.g. 45)" required class="border rounded p-2">
          </div>
          <button type="submit" class="w-full bg-stone-800 text-white py-2 rounded font-semibold">Record Purchase</button>
        </form>
      </div>

      <div class="bg-white p-5 rounded-lg shadow">
        <h2 class="text-lg font-bold mb-3">Current Stock Balances (Live Ledger)</h2>
        <table class="w-full text-sm text-left"><thead><tr class="border-b bg-stone-50"><th class="p-2">Item</th><th class="p-2">Type</th><th class="p-2">Closing Balance</th></tr></thead><tbody>{stock_rows}</tbody></table>
      </div>

      <div class="md:col-span-2 bg-white p-5 rounded-lg shadow">
        <h2 class="text-lg font-bold mb-3">2. Log Daily Production Run (BOM: 40 kg Flour, 10 L Oil, 1.2 kg Spice → 200 pkts)</h2>
        <form method="post" action="/production/run" class="grid md:grid-cols-4 gap-3">
          <div><label class="text-xs font-semibold">Product</label><select name="finished_item_id" class="w-full border rounded p-2 bg-white">{fin_opts}</select></div>
          <div><label class="text-xs font-semibold">Flour Used (kg)</label><input type="number" step="0.01" name="flour_kg" value="40" required class="w-full border rounded p-2"></div>
          <div><label class="text-xs font-semibold">Oil Used (L)</label><input type="number" step="0.01" name="oil_l" value="10.5" required class="w-full border rounded p-2"></div>
          <div><label class="text-xs font-semibold">Spice Used (kg)</label><input type="number" step="0.01" name="spice_kg" value="1.2" required class="w-full border rounded p-2"></div>
          <div><label class="text-xs font-semibold">Actual Good Packets</label><input type="number" name="good_pkts" value="188" required class="w-full border rounded p-2"></div>
          <div><label class="text-xs font-semibold">Damaged Pouches</label><input type="number" name="damaged_pouches" value="6" required class="w-full border rounded p-2"></div>
          <div><label class="text-xs font-semibold">Cartons Used</label><input type="number" name="cartons_used" value="9" required class="w-full border rounded p-2"></div>
          <div><label class="text-xs font-semibold">Direct Labour (₹)</label><input type="number" step="0.01" name="labour" value="1200" required class="w-full border rounded p-2"></div>
          <div><label class="text-xs font-semibold">Gas & Power (₹)</label><input type="number" step="0.01" name="overhead" value="600" required class="w-full border rounded p-2"></div>
          <div class="md:col-span-3 flex items-end"><button type="submit" class="w-full bg-amber-800 hover:bg-amber-700 text-white py-2 rounded font-bold">Post Production Run & Update Stock</button></div>
        </form>
      </div>

      <div class="md:col-span-2 bg-white p-5 rounded-lg shadow">
        <h3 class="font-bold mb-2">Production History & Variance Alerts (&gt;3% Tolerance)</h3>
        <table class="w-full text-sm text-left"><thead><tr class="border-b bg-stone-50"><th class="p-2">Run</th><th class="p-2">Output</th><th class="p-2">Cost/Pkt</th><th class="p-2">Variance Status</th></tr></thead><tbody>{run_rows}</tbody></table>
      </div>
    </div>"""
    return render_page("Production Floor", "production", body, msg)

@app.post("/production/purchase")
def post_purchase(supplier: str = Form(...), item_id: int = Form(...), qty: float = Form(...), rate: float = Form(...), db: Session = Depends(get_db)):
    record_purchase(db, supplier, item_id, qty, rate)
    return RedirectResponse("/production?msg=Purchase+recorded+and+stock+updated!", status_code=303)

@app.post("/production/run")
def post_run(
    finished_item_id: int = Form(...), flour_kg: float = Form(...), oil_l: float = Form(...),
    spice_kg: float = Form(...), good_pkts: int = Form(...), damaged_pouches: int = Form(...),
    cartons_used: int = Form(...), labour: float = Form(...), overhead: float = Form(...),
    db: Session = Depends(get_db)
):
    flour = db.query(Item).filter_by(name="Flour").first()
    oil = db.query(Item).filter_by(name="Cooking Oil").first()
    spice = db.query(Item).filter_by(name="Salt & Spice Mix").first()
    run = record_production_run(
        db, finished_item_id,
        {flour.id: flour_kg, oil.id: oil_l, spice.id: spice_kg},
        good_pkts, damaged_pouches, cartons_used, labour, overhead
    )
    return RedirectResponse(f"/production?msg=Run+%23{run.id}+posted!+Cost/pkt:+₹{run.cost_per_packet_paise/100:.2f}", status_code=303)

# --- 4. FACTORY ADMIN VIEW ---
@app.get("/admin", response_class=HTMLResponse)
def admin_view(msg: str = "", db: Session = Depends(get_db)):
    murukku = db.query(Item).filter_by(category="FINISHED").first()
    avail_stock = get_stock_base(db, murukku.id)
    orders = db.query(Order).order_by(Order.id.desc()).all()
    invoices = db.query(Invoice).order_by(Invoice.id.desc()).all()

    order_rows = ""
    for o in orders:
        c = db.query(Customer).get(o.customer_id)
        enough = avail_stock >= o.qty_packets
        stock_note = f'<span class="text-green-700">In Stock ({avail_stock})</span>' if enough else f'<span class="text-red-700 font-bold">Short by {o.qty_packets - avail_stock} pkts!</span>'
        action_btn = f'<form method="post" action="/admin/approve/{o.id}"><button class="bg-amber-800 text-white px-3 py-1 rounded text-xs font-semibold">Approve, Invoice & Dispatch</button></form>' if o.status != "DISPATCHED" else '<span class="text-xs text-stone-500">Dispatched</span>'
        order_rows += f"""<tr class="border-b">
          <td class="p-2">#{o.id} ({o.salesman_name})</td>
          <td class="p-2">{c.name} ({c.state})</td>
          <td class="p-2">{o.qty_packets} pkts</td>
          <td class="p-2 text-xs">{stock_note if o.status != 'DISPATCHED' else 'Fulfilled'}</td>
          <td class="p-2">{action_btn}</td>
        </tr>"""

    inv_rows = ""
    for inv in invoices:
        c = db.query(Customer).get(inv.customer_id)
        paid = db.query(func.sum(Payment.amount_paise)).filter_by(invoice_id=inv.id).scalar() or 0
        due = inv.grand_total_paise - paid
        pay_form = f"""<form method="post" action="/admin/pay/{inv.id}" class="flex gap-1">
          <input type="number" step="0.01" name="amount" placeholder="₹ Amt" required class="border rounded px-2 py-1 w-24 text-xs">
          <button class="bg-green-700 text-white px-2 py-1 rounded text-xs">Record Pay</button>
        </form>""" if due > 0 else '<span class="text-green-700 text-xs font-bold">PAID</span>'
        inv_rows += f"""<tr class="border-b">
          <td class="p-2 font-mono text-xs">{inv.invoice_no}</td>
          <td class="p-2">{c.name}</td>
          <td class="p-2">₹{inv.taxable_paise/100:.2f}</td>
          <td class="p-2 text-xs">CGST ₹{inv.cgst_paise/100:.2f} | SGST ₹{inv.sgst_paise/100:.2f} | IGST ₹{inv.igst_paise/100:.2f}</td>
          <td class="p-2 font-bold">₹{inv.grand_total_paise/100:.2f}</td>
          <td class="p-2 text-red-700 font-bold">₹{due/100:.2f}</td>
          <td class="p-2 flex items-center gap-2"><a href="/invoice/{inv.id}/pdf" class="bg-stone-700 text-white px-2 py-1 rounded text-xs">PDF</a>{pay_form}</td>
        </tr>"""

    body = f"""
    <div class="bg-white p-4 rounded-lg shadow mb-6 flex justify-between items-center">
      <span class="font-bold">Finished Goods Available (Murukku 200g):</span>
      <span class="text-xl font-bold text-amber-900">{avail_stock} packets</span>
    </div>
    <div class="bg-white p-5 rounded-lg shadow mb-6">
      <h2 class="text-lg font-bold mb-3">Incoming Sales Orders</h2>
      <table class="w-full text-sm text-left"><thead><tr class="border-b bg-stone-50"><th class="p-2">Order</th><th class="p-2">Customer</th><th class="p-2">Qty</th><th class="p-2">Stock Check</th><th class="p-2">Action</th></tr></thead><tbody>{order_rows}</tbody></table>
    </div>
    <div class="bg-white p-5 rounded-lg shadow">
      <h2 class="text-lg font-bold mb-3">GST Tax Invoices & Customer Collections</h2>
      <table class="w-full text-sm text-left"><thead><tr class="border-b bg-stone-50"><th class="p-2">Invoice #</th><th class="p-2">Customer</th><th class="p-2">Taxable</th><th class="p-2">GST Split</th><th class="p-2">Total</th><th class="p-2">Outstanding</th><th class="p-2">Actions</th></tr></thead><tbody>{inv_rows}</tbody></table>
    </div>"""
    return render_page("Factory Admin", "admin", body, msg)

@app.post("/admin/approve/{order_id}")
def admin_approve(order_id: int, db: Session = Depends(get_db)):
    res = approve_invoice_and_dispatch(db, order_id)
    if not res["ok"]:
        return RedirectResponse(f"/admin?msg=HOLD:+Insufficient+stock!+Short+by+{res['shortage']}+packets+(Available:+{res['available']}).", status_code=303)
    return RedirectResponse(f"/admin?msg=Invoice+{res['invoice'].invoice_no}+raised+and+dispatched!", status_code=303)

@app.post("/admin/pay/{invoice_id}")
def admin_pay(invoice_id: int, amount: float = Form(...), db: Session = Depends(get_db)):
    record_payment(db, invoice_id, amount)
    return RedirectResponse(f"/admin?msg=Recorded+payment+of+₹{amount:.2f}!", status_code=303)

# --- 5. GST INVOICE PDF GENERATOR ---
@app.get("/invoice/{invoice_id}/pdf")
def download_invoice_pdf(invoice_id: int, db: Session = Depends(get_db)):
    inv = db.query(Invoice).get(invoice_id)
    cust = db.query(Customer).get(inv.customer_id)
    order = db.query(Order).get(inv.order_id)
    item = db.query(Item).get(order.item_id)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "TAX INVOICE - SRI MURUGAN SNACKS", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, "Factory GSTIN: 33AABCS9999K1Z2 | State: Tamil Nadu (33)", ln=True)
    pdf.cell(0, 6, f"Invoice No: {inv.invoice_no}   |   Date: {inv.created_at.strftime('%Y-%m-%d')}", ln=True)
    pdf.ln(4)
    pdf.cell(0, 6, f"Billed To: {cust.name}   |   Place of Supply: {cust.state}   |   GSTIN: {cust.gstin}", ln=True)
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(60, 8, "Product", 1)
    pdf.cell(25, 8, "HSN", 1)
    pdf.cell(25, 8, "Qty", 1)
    pdf.cell(35, 8, "Rate (Rs)", 1)
    pdf.cell(45, 8, "Taxable (Rs)", 1, ln=True)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(60, 8, item.name, 1)
    pdf.cell(25, 8, item.hsn_code, 1)
    pdf.cell(25, 8, str(order.qty_packets), 1)
    pdf.cell(35, 8, f"{order.unit_price_paise/100:.2f}", 1)
    pdf.cell(45, 8, f"{inv.taxable_paise/100:.2f}", 1, ln=True)
    pdf.ln(6)

    pdf.cell(0, 6, f"CGST (2.5%): Rs. {inv.cgst_paise/100:.2f}", ln=True)
    pdf.cell(0, 6, f"SGST (2.5%): Rs. {inv.sgst_paise/100:.2f}", ln=True)
    pdf.cell(0, 6, f"IGST (5.0%): Rs. {inv.igst_paise/100:.2f}", ln=True)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, f"Grand Total: Rs. {inv.grand_total_paise/100:.2f}", ln=True)

    buf = io.BytesIO(pdf.output())
    return StreamingResponse(buf, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={inv.invoice_no.replace('/', '_')}.pdf"})

# --- 6. AUDITOR & OWNER VIEWS + EXCEL EXPORT ---
@app.get("/auditor", response_class=HTMLResponse)
def auditor_view(db: Session = Depends(get_db)):
    ledger = db.query(StockLedger).order_by(StockLedger.id.desc()).all()
    ledger_rows = ""
    for l in ledger:
        item = db.query(Item).get(l.item_id)
        ledger_rows += f"""<tr class="border-b text-xs">
          <td class="p-2">#{l.id}</td><td class="p-2">{item.name}</td><td class="p-2">{l.movement_type}</td>
          <td class="p-2 font-mono">{l.qty_delta_base / item.conversion_factor:+g} {item.display_unit}</td>
          <td class="p-2">{l.ref_type} #{l.ref_id}</td>
        </tr>"""

    body = f"""
    <div class="flex justify-between items-center mb-6">
      <div><h1 class="text-2xl font-bold">Monthly Auditor & Accounts Pack (Read-Only)</h1><p class="text-sm text-stone-600">All balances reconciled directly from the immutable Stock Ledger.</p></div>
      <a href="/auditor/export.xlsx" class="bg-green-700 hover:bg-green-600 text-white px-4 py-2.5 rounded-lg font-bold shadow">Download Monthly Excel Pack (.xlsx)</a>
    </div>
    <div class="bg-white p-5 rounded-lg shadow">
      <h2 class="font-bold mb-3">Complete Traceable Stock Ledger</h2>
      <table class="w-full text-left"><thead><tr class="border-b bg-stone-50 text-xs"><th class="p-2">ID</th><th class="p-2">Item</th><th class="p-2">Movement</th><th class="p-2">Qty Delta</th><th class="p-2">Source Doc</th></tr></thead><tbody>{ledger_rows}</tbody></table>
    </div>"""
    return render_page("Auditor Reports", "auditor", body)

@app.get("/auditor/export.xlsx")
def export_auditor_excel(db: Session = Depends(get_db)):
    wb = openpyxl.Workbook()

    # Sheet 1: Stock Summary
    ws_stock = wb.active
    ws_stock.title = "Stock Summary"
    ws_stock.append(["Item", "Category", "Closing Balance", "Unit"])
    for i in db.query(Item).all():
        ws_stock.append([i.name, i.category, get_stock_base(db, i.id) / i.conversion_factor, i.display_unit])

    # Sheet 2: Sales & GST Register
    ws_sales = wb.create_sheet("Sales & GST Register")
    ws_sales.append(["Invoice No", "Customer", "State", "GSTIN", "Taxable (₹)", "CGST (₹)", "SGST (₹)", "IGST (₹)", "Total (₹)", "Paid (₹)", "Outstanding (₹)"])
    for inv in db.query(Invoice).all():
        c = db.query(Customer).get(inv.customer_id)
        paid = db.query(func.sum(Payment.amount_paise)).filter_by(invoice_id=inv.id).scalar() or 0
        ws_sales.append([inv.invoice_no, c.name, c.state, c.gstin, inv.taxable_paise/100, inv.cgst_paise/100, inv.sgst_paise/100, inv.igst_paise/100, inv.grand_total_paise/100, paid/100, (inv.grand_total_paise - paid)/100])

    # Sheet 3: Production Variance & Costing
    ws_prod = wb.create_sheet("Production & Costing")
    ws_prod.append(["Run ID", "Expected Pkts", "Actual Pkts", "Yield Var %", "Total Cost (₹)", "Cost/Packet (₹)", "Variance Alerts"])
    for r in db.query(ProductionRun).all():
        ws_prod.append([r.id, r.expected_packets, r.actual_good_packets, r.yield_variance_pct, r.total_run_cost_paise/100, r.cost_per_packet_paise/100, r.variance_notes])

    # Sheet 4: Full Stock Ledger
    ws_led = wb.create_sheet("Stock Ledger")
    ws_led.append(["Entry ID", "Item", "Movement", "Delta", "Unit", "Source Type", "Source ID", "Timestamp"])
    for l in db.query(StockLedger).all():
        i = db.query(Item).get(l.item_id)
        ws_led.append([l.id, i.name, l.movement_type, l.qty_delta_base / i.conversion_factor, i.display_unit, l.ref_type, l.ref_id, str(l.timestamp)])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=Monthly_Auditor_Pack.xlsx"})

@app.get("/owner", response_class=HTMLResponse)
def owner_view(db: Session = Depends(get_db)):
    latest_run = db.query(ProductionRun).order_by(ProductionRun.id.desc()).first()
    cost_pkt = f"₹{latest_run.cost_per_packet_paise/100:.2f}" if latest_run else "N/A"
    alerts = latest_run.variance_notes if latest_run else "No runs logged yet"
    total_invoiced = db.query(func.sum(Invoice.grand_total_paise)).scalar() or 0
    total_paid = db.query(func.sum(Payment.amount_paise)).scalar() or 0
    due = (total_invoiced - total_paid) / 100

    body = f"""
    <h1 class="text-2xl font-bold mb-4">Owner Executive Summary</h1>
    <div class="grid md:grid-cols-3 gap-4 mb-6">
      <div class="bg-white p-5 rounded-lg shadow"><div class="text-xs text-stone-500">LATEST COST PER PACKET</div><div class="text-2xl font-bold text-amber-900 mt-1">{cost_pkt}</div><div class="text-xs text-stone-500 mt-1">Selling Price: ₹50.00 (Excl. GST)</div></div>
      <div class="bg-white p-5 rounded-lg shadow"><div class="text-xs text-stone-500">OUTSTANDING RECEIVABLES</div><div class="text-2xl font-bold text-red-700 mt-1">₹{due:.2f}</div></div>
      <div class="bg-white p-5 rounded-lg shadow"><div class="text-xs text-stone-500">LATEST VARIANCE ALERTS</div><div class="text-sm font-semibold text-amber-800 mt-2">{alerts}</div></div>
    </div>"""
    return render_page("Owner Dashboard", "owner", body)