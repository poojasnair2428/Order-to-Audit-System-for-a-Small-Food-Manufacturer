from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# 1. Create a local SQLite database file named 'factory.db'
DATABASE_URL = "sqlite:///./factory.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- TABLES ---

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    role = Column(String)  # 'salesman', 'admin', 'production', 'auditor', 'owner'

class Item(Base):
    """Stores Raw Materials, Packaging, AND Finished Goods"""
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)       # e.g., "Flour", "Murukku 200g"
    category = Column(String)                # 'RAW', 'PACKAGING', 'FINISHED'
    base_unit = Column(String)               # Store in base units: 'g', 'ml', 'pcs'
    display_unit = Column(String)            # What humans read: 'kg', 'L', 'packets'
    conversion_factor = Column(Integer)      # e.g., 1000 (1 kg = 1000 g), 1 for pcs
    selling_price_paise = Column(Integer, default=0)  # Stored in paise (₹50 = 5000)
    hsn_code = Column(String, default="210690")
    gst_rate = Column(Float, default=5.0)    # 5% GST

class RecipeBOM(Base):
    """Defines what 1 batch of a Finished Product needs"""
    __tablename__ = "bom_items"
    id = Column(Integer, primary_key=True, index=True)
    finished_item_id = Column(Integer, ForeignKey("items.id"))
    ingredient_item_id = Column(Integer, ForeignKey("items.id"))
    std_qty_base = Column(Integer)           # Standard qty per batch in base units (e.g., 40000 g)
    expected_yield_pcs = Column(Integer)     # e.g., 200 packets per batch

class StockLedger(Base):
    """THE HEART OF THE SYSTEM: Every + or - movement is logged here"""
    __tablename__ = "stock_ledger"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"))
    movement_type = Column(String)           # 'OPENING', 'PURCHASE', 'PROD_ISSUE', 'PROD_OUTPUT', 'WASTAGE', 'DISPATCH'
    qty_delta_base = Column(Integer)         # Positive (+60000 g) or Negative (-40000 g)
    unit_cost_paise = Column(Integer)        # Cost per base/display unit in paise
    ref_type = Column(String)                # 'SEED', 'PURCHASE', 'PRODUCTION', 'INVOICE'
    ref_id = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)                    # e.g., "Retailer A", "Distributor B"
    state = Column(String)                   # "Tamil Nadu" vs "Karnataka" (decides CGST/SGST vs IGST!)
    gstin = Column(String)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    salesman_name = Column(String)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    item_id = Column(Integer, ForeignKey("items.id"))
    qty_packets = Column(Integer)
    unit_price_paise = Column(Integer)
    status = Column(String, default="SUBMITTED")  # SUBMITTED -> INVOICED -> DISPATCHED
    created_at = Column(DateTime, default=datetime.utcnow)

# Helper function to create all tables
def init_db():
    Base.metadata.create_all(bind=engine)