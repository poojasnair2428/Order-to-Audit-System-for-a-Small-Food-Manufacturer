from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./factory.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    role = Column(String)  # 'salesman', 'admin', 'production', 'auditor', 'owner'

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    category = Column(String)                # 'RAW', 'PACKAGING', 'FINISHED'
    base_unit = Column(String)               # 'g', 'ml', 'pcs'
    display_unit = Column(String)            # 'kg', 'L', 'packets', 'pcs'
    conversion_factor = Column(Integer)      # 1000 for kg/L, 1 for pcs
    selling_price_paise = Column(Integer, default=0)
    hsn_code = Column(String, default="210690")
    gst_rate = Column(Float, default=5.0)

class RecipeBOM(Base):
    __tablename__ = "bom_items"
    id = Column(Integer, primary_key=True, index=True)
    finished_item_id = Column(Integer, ForeignKey("items.id"))
    ingredient_item_id = Column(Integer, ForeignKey("items.id"))
    std_qty_base = Column(Integer)           # Standard qty per batch in base units
    expected_yield_pcs = Column(Integer)     # Expected packets per batch (200)

class StockLedger(Base):
    __tablename__ = "stock_ledger"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"))
    movement_type = Column(String)           # 'OPENING', 'PURCHASE', 'PROD_ISSUE', 'PROD_OUTPUT', 'WASTAGE', 'DISPATCH'
    qty_delta_base = Column(Integer)         # + or - in base units
    unit_cost_paise = Column(Integer)        # Cost per display unit in paise
    ref_type = Column(String)                # 'SEED', 'PURCHASE', 'PRODUCTION', 'INVOICE'
    ref_id = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Purchase(Base):
    __tablename__ = "purchases"
    id = Column(Integer, primary_key=True, index=True)
    supplier_name = Column(String)
    item_id = Column(Integer, ForeignKey("items.id"))
    qty_base = Column(Integer)
    rate_per_display_unit_paise = Column(Integer)
    total_paise = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

class ProductionRun(Base):
    __tablename__ = "production_runs"
    id = Column(Integer, primary_key=True, index=True)
    finished_item_id = Column(Integer, ForeignKey("items.id"))
    batches = Column(Float, default=1.0)
    expected_packets = Column(Integer)
    actual_good_packets = Column(Integer)
    damaged_pouches = Column(Integer, default=0)
    cartons_used = Column(Integer, default=0)
    yield_variance_pct = Column(Float)
    yield_flagged = Column(Boolean, default=False)
    labour_cost_paise = Column(Integer, default=0)
    overhead_cost_paise = Column(Integer, default=0)
    total_run_cost_paise = Column(Integer, default=0)
    cost_per_packet_paise = Column(Integer, default=0)
    variance_notes = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    state = Column(String)                   # 'Tamil Nadu' vs 'Karnataka'
    gstin = Column(String)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    salesman_name = Column(String)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    item_id = Column(Integer, ForeignKey("items.id"))
    qty_packets = Column(Integer)
    unit_price_paise = Column(Integer)
    status = Column(String, default="SUBMITTED")  # SUBMITTED -> INVOICED / SHORTAGE_HOLD
    created_at = Column(DateTime, default=datetime.utcnow)

class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, index=True)
    invoice_no = Column(String, unique=True)  # e.g., INV/26-27/0001
    order_id = Column(Integer, ForeignKey("orders.id"))
    customer_id = Column(Integer, ForeignKey("customers.id"))
    taxable_paise = Column(Integer)
    cgst_paise = Column(Integer, default=0)
    sgst_paise = Column(Integer, default=0)
    igst_paise = Column(Integer, default=0)
    grand_total_paise = Column(Integer)
    dispatched = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    customer_id = Column(Integer, ForeignKey("customers.id"))
    amount_paise = Column(Integer)
    mode = Column(String, default="NEFT/UPI")
    created_at = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String)
    action = Column(String)
    details = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)