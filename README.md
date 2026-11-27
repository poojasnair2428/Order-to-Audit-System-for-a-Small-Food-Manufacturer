# Order-to-Audit ERP System — Sri Murugan Snacks

**Submitted for:** Winter Internship Shortlisting Task — Centre for Digital Infrastructure, NIT Tiruchirappalli  
**Domain:** End-to-End Manufacturing, Inventory Ledger, GST Billing & Audit Reporting for a Small-Scale Packaged Snacks Factory  
**Demo Video:** `<PASTE_YOUR_UNLISTED_YOUTUBE_OR_DRIVE_LINK_HERE>`

---

## 1. Overview & Problem Solved

Small-scale food manufacturers typically manage field orders over phone/WhatsApp, billing in standalone tools, and production/inventory on paper. This creates re-entry errors, untracked raw-material wastage, unknown unit costs, and manual month-end reconciliation.

This prototype implements a **single-entry, ledger-driven Order-to-Audit system** linking two operational loops at **Finished Goods Inventory**:
1. **Sales Loop:** Mobile Field Order -> Admin Stock Verification -> GST Tax Invoice (CGST+SGST / IGST) -> Dispatch (stock deduction) -> Collections & Receivables.
2. **Production Loop:** Raw Material Purchase -> BOM-Based Production Run (planned vs. actual consumption & yield) -> Variance Flagging (>3%) -> Finished Goods Addition & Cost-per-Packet Computation.

---

## 2. Tech Stack & Justification

* **Backend (`Python 3.11` + `FastAPI`):** Selected for clean, readable business logic, rapid form/API routing, and strict server-side validation without boilerplate overhead.
* **Database & ORM (`SQLite` + `SQLAlchemy`):** Zero-configuration relational persistence bundled cleanly for single-command local execution and Docker deployment. Inventory balances are derived dynamically from an append-only `StockLedger` table rather than mutable balance columns.
* **Frontend & Document Exports (`HTML` + `Tailwind CSS`, `fpdf2`, `openpyxl`):** Server-rendered responsive interfaces tailored to mobile field salesmen and desktop factory staff (including a bilingual English/Tamil floor UI), paired with compliant GST PDF invoice generation and multi-sheet Excel workbooks for auditors.

---

## 3. Setup & Single-Command Run Instructions

### Option A: Run Locally with Python
1. Clone the repository and enter the project folder:
   ```bash
   git clone <your-repo-url>
   cd snack-erp
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # macOS / Linux:
   source venv/bin/activate
   ```
3. Install dependencies and load the Section 5 benchmark master data:
   ```bash
   pip install -r requirements.txt
   python seed.py
   ```
4. Start the application server:
   ```bash
   uvicorn app:app --reload
   ```
5. Open **`http://127.0.0.1:8000`** in your browser.

### Option B: Run with Docker (Single Command)
```bash
docker build -t snack-erp .
docker run -p 8000:8000 snack-erp
```
Open **`http://127.0.0.1:8000`** in your browser.

### Test Logins / Role Access
Select any role directly from the home screen (`/`):
* **Salesman (`salesman_a`, `salesman_b`):** Mobile-friendly order entry & order status tracker (`/salesman`)
* **Production Supervisor (`supervisor`):** Raw-material purchase logging, live stock view, production planner & BOM production run entry in English/Tamil (`/production`)
* **Factory Admin (`admin`):** Order verification, stock shortage check, GST invoicing, PDF download & payment recording (`/admin`)
* **Accountant / Auditor (`auditor`):** Read-only traceable stock ledger & monthly Excel report download (`/auditor`)
* **Factory Owner (`owner`):** Executive KPI dashboard showing unit cost, receivables & variance alerts (`/owner`)

---

## 4. Feature Coverage Against Scope (Section 6)

| Tier | Feature | Status | Implementation Details |
| :--- | :--- | :--- | :--- |
| **Must Have** | Role-based access (Salesman, Admin, Production, Auditor, Owner) | Implemented | Dedicated role workspaces restricting views and actions per user role |
| **Must Have** | Product, Customer, Raw-Material & BOM masters | Implemented | Pre-seeded via `seed.py` with unit conversion factors (`kg/g`, `L/ml`, `pcs`) |
| **Must Have** | Mobile-friendly order entry & admin approval | Implemented | Responsive mobile form for field salesmen; stock-checked approval desk for admin |
| **Must Have** | GST-compliant PDF invoice | Implemented | Generates downloadable PDF with HSN `210690`, GSTINs, and CGST+SGST / IGST split |
| **Must Have** | BOM production run with automatic stock updates | Implemented | Deducts raw materials, good pouches, damaged pouches, and cartons; adds finished goods |
| **Must Have** | Planned vs. actual consumption & yield variance | Implemented | Computes percentage deviation per raw ingredient and overall batch yield |
| **Must Have** | Stock summary & traceable stock ledger | Implemented | Every movement links back to `SEED`, `PURCHASE`, `PRODUCTION`, or `INVOICE` |
| **Must Have** | Exportable sales & stock reports | Implemented | Multi-sheet `.xlsx` auditor workbook (`Stock Summary`, `Sales & GST`, `Production`, `Ledger`) |
| **Should Have** | Supplier purchases & customer payment tracking | Implemented | Tracks partial payments against invoices and computes live customer dues |
| **Should Have** | Cost per packet with overheads | Implemented | Weighted-average material valuation + direct batch labour & power/gas allocation |
| **Should Have** | Variance alerts beyond tolerance (`>3%`) | Implemented | Automatically flags deviations exceeding +/- 3% on production runs and Owner dashboard |
| **Should Have** | Owner executive dashboard | Implemented | Live summary of latest unit cost, gross margin, receivables, and variance alerts |
| **Stretch Goal** | Production planning from pending orders | Implemented | Calculates net shortfall (`pending orders - available stock`) and recommends exact batches needed |
| **Stretch Goal** | Tamil language interface for floor staff | Implemented | One-click `EN / தமிழ்` toggle on the Production Supervisor floor workspace |

---

## 5. Section 5 Benchmark Results & Verification

Running `python test_benchmark.py` (or executing Steps 1–9 through the UI) produces the exact expected results:

| Benchmark Check | System Output | Expected | Verification & Calculation |
| :--- | :--- | :--- | :--- |
| **Flour Closing Balance** | **120.0 kg** | 120 kg | `100 kg opening + 60 kg purchase - 40 kg issued` |
| **Cooking Oil Closing Balance** | **19.5 L** | 19.5 L | `30 L opening - 10.5 L issued` |
| **200g Pouches Closing Balance** | **306 pcs** | 306 pcs | `500 opening - (188 good packets + 6 damaged pouches)` |
| **Finished Goods (Post-Run)** | **238 packets** | 238 packets | `50 opening + 188 good packets produced` |
| **Finished Goods (Post-Dispatch)** | **88 packets** | 88 packets | `238 available - 150 dispatched to Retailer A` |
| **Yield Variance** | **-6.0% (Flagged)** | -6%, flagged | `(188 actual - 200 expected) / 200 = -6.0%` (>3% tolerance) |
| **Oil Consumption Variance** | **+5.0% (Flagged)** | +5%, flagged | `(10.5 L actual - 10.0 L std) / 10.0 L = +5.0%` (>3% tolerance) |
| **Retailer A Invoice (Tamil Nadu)** | **Rs. 7,875.00** | Rs. 7,875.00 | `Rs. 7,500.00 taxable + Rs. 187.50 CGST (2.5%) + Rs. 187.50 SGST (2.5%)` |
| **Retailer A Outstanding Balance** | **Rs. 3,875.00** | Rs. 3,875.00 | `Rs. 7,875.00 grand total - Rs. 4,000.00 payment received` |
| **Distributor B Order (Karnataka)** | **Shortage: 32 pkts** | Shortage of 32 | `120 ordered vs. 88 available`; 5% IGST applies when invoiced |
| **Cost per Packet** | **Rs. 31.14 / packet** | Stated & justified | See costing breakdown below |

### Valuation & Overhead Methodology
1. **Raw Material Valuation — Weighted Average Cost:**
   * Flour opening balance: `100 kg @ Rs. 42.00/kg = Rs. 4,200.00`
   * Flour new purchase: `60 kg @ Rs. 45.00/kg = Rs. 2,700.00`
   * Weighted average rate: `Rs. 6,900.00 / 160 kg = Rs. 43.125/kg`
2. **Direct Material & Packaging Cost for Run #1:**
   * Flour: `40.0 kg x Rs. 43.125 = Rs. 1,725.00`
   * Cooking Oil: `10.5 L x Rs. 140.00 = Rs. 1,470.00`
   * Salt & Spice Mix: `1.2 kg x Rs. 200.00 = Rs. 240.00`
   * 200g Pouches (188 good + 6 damaged = 194 consumed): `194 x Rs. 2.50 = Rs. 485.00`
   * Cartons: `9 x Rs. 15.00 = Rs. 135.00`
   * **Subtotal Materials & Packaging:** `Rs. 4,055.00`
3. **Overhead Allocation Rule:**
   * Direct batch labour (`Rs. 1,200.00`) and gas/power (`Rs. 600.00`) entered against the production run are allocated 100% to that batch's good output (`Rs. 1,800.00`).
4. **Final Unit Cost & Margin:**
   * Total Run Cost: `Rs. 4,055.00 + Rs. 1,800.00 = Rs. 5,855.00`
   * Cost per Good Packet: `Rs. 5,855.00 / 188 packets` = **Rs. 31.14 / packet**
   * Gross Margin vs. Rs. 50.00 Selling Price: **Rs. 18.86 / packet (37.7%)**

---

## 6. Key Design Assumptions & Known Gaps

### Assumptions
* **Zero Floating-Point Drift:** All physical quantities are stored as integers in base units (`g`, `ml`, `pcs`), and all financial amounts are stored as integer `paise` (`Rs. 1.00 = 100 paise`).
* **Place-of-Supply GST Logic:** The factory is registered in **Tamil Nadu**. Orders from customers in Tamil Nadu automatically split 5% GST into `2.5% CGST + 2.5% SGST`; orders from outside Tamil Nadu (e.g., Karnataka) apply `5.0% IGST`.
* **Stock Reservation Policy:** Finished goods are deducted upon invoice dispatch. Orders exceeding current available stock are placed on `SHORTAGE_HOLD` with exact shortfall quantities displayed to the admin.

### Known Gaps (Planned Enhancements)
* **Offline Sync Queue:** Adding Service Worker + IndexedDB/localStorage caching so field salesmen in zero-signal areas can queue orders offline and auto-sync when connectivity returns.
* **Batch & Expiry Tracking (FEFO):** Tracking lot numbers and best-before dates on food batches to enforce First-Expiry-First-Out dispatch.
* **Credit Note Workflow:** Supporting post-invoice cancellations/returns via formal GST Credit Notes rather than direct edits.

---

## 7. Repository Structure

```text
snack-erp/
├── models.py           # SQLAlchemy relational database schema & ledger tables
├── seed.py             # Loads Section 5 master data, BOM, opening balances & customers
├── engine.py           # Core business logic: weighted-avg costing, BOM variance, GST & ledger ops
├── app.py              # FastAPI web application, role-based UI, Tamil toggle, PDF invoice & Excel export
├── test_benchmark.py   # Automated verification script for Section 5 benchmark checks
├── requirements.txt    # Python dependencies
├── Dockerfile          # Single-command container setup
├── DESIGN_NOTE.md      # 2-page architectural & ER design note
└── README.md           # Project setup, scope coverage & benchmark documentation
```