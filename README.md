# Order-to-Audit ERP System — Sri Murugan Snacks

**Submitted for:** Summer/Winter Internship Shortlisting Task — Centre for Digital Infrastructure, NIT Tiruchirappalli  
**Domain:** End-to-End Manufacturing, Inventory Ledger, GST Billing & Audit Reporting for a Small-Scale Packaged Snacks Factory

---

## 1. Overview & Problem Solved

Small-scale food manufacturers typically manage field orders over phone/WhatsApp, billing in standalone tools, and production/inventory on paper. This creates re-entry errors, untracked raw-material wastage, unknown unit costs, and manual month-end reconciliation.

This prototype implements a **single-entry, ledger-driven Order-to-Audit system** linking two operational loops at **Finished Goods Inventory**:
1. **Sales Loop:** Mobile Field Order $\rightarrow$ Admin Stock Verification $\rightarrow$ GST Tax Invoice (CGST+SGST / IGST) $\rightarrow$ Dispatch (stock deduction) $\rightarrow$ Collections & Receivables.
2. **Production Loop:** Raw Material Purchase $\rightarrow$ BOM-Based Production Run (planned vs. actual consumption & yield) $\rightarrow$ Variance Flagging ($>3\%$) $\rightarrow$ Finished Goods Addition & Cost-per-Packet Computation.

---

## 2. Tech Stack & Justification

* **Backend (`Python 3.11` + `FastAPI`):** Selected for clean, readable business logic, rapid form/API routing, and strict server-side validation without boilerplate overhead.
* **Database & ORM (`SQLite` + `SQLAlchemy`):** Zero-configuration relational persistence bundled cleanly for single-command local execution and Docker deployment. Inventory balances are derived dynamically from an append-only `StockLedger` table rather than mutable balance columns.
* **Frontend & Document Exports (`HTML` + `Tailwind CSS`, `fpdf2`, `openpyxl`):** Server-rendered responsive interfaces tailored to mobile field salesmen and desktop factory staff, paired with compliant GST PDF invoice generation and multi-sheet Excel workbooks for auditors.

---

## 3. Setup & Single-Command Run Instructions

### Option A: Run Locally with Python
1. Clone the repository and enter the project folder:
   ```bash
   git clone <your-repo-url>
   cd snack-erp
 ```

1.Create and activate a virtual environment:

 ```bash
 python -m venv venv
 # Windows:
.\venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate
```
 
 
2.Install dependencies and load the Section 5 benchmark master data:

 ```bash
 pip install -r requirements.txt
 python seed.py
```

3.Start the application server:

 ```bash
 uvicorn app:app --reload
```
