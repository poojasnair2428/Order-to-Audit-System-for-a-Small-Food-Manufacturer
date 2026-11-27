# System Design Note: Order-to-Audit ERP for a Small Food Manufacturer

**Project:** Sri Murugan Snacks — Order-to-Audit System  
**Submission for:** Centre for Digital Infrastructure, NIT Tiruchirappalli

---

## 1. Core Architectural Principle: Immutable Stock Ledger

In traditional inventory spreadsheets or simple CRUD apps, stock balances are stored as a mutable `quantity_on_hand` column that gets overwritten on purchases, production runs, or dispatches. Overwriting balances destroys auditability and causes silent drift when edits or partial dispatches occur.

In this system, **stock is never overwritten**. Instead, every physical movement is recorded as an append-only row in the `StockLedger` table, and current stock is computed dynamically:

$$\text{Closing Balance} = \text{Opening} + \sum \text{Receipts} - \sum \text{Issues/Sales} \pm \sum \text{Adjustments} = \sum \text{qty\_delta\_base}$$

Every ledger entry stores:
* **`qty_delta_base`:** Signed integer in normalized base units (`+60000` g for purchase, `-40000` g for production issue, `-150` pcs for dispatch).
* **`ref_type` & `ref_id`:** Foreign reference back to the exact source document (`SEED`, `PURCHASE`, `PRODUCTION`, or `INVOICE`), giving the monthly auditor 100% end-to-end traceability.

---

## 2. Relational Data Model (ER Diagram)

```text
+------------------+       +--------------------+       +-----------------------+
|      User        |       |      Customer      |       |       AuditLog        |
+------------------+       +--------------------+       +-----------------------+
| id (PK)          |       | id (PK)            |       | id (PK)               |
| username         |       | name               |       | username              |
| role             |       | state (TN / KA)    |       | action                |
+------------------+       | gstin              |       | details, timestamp    |
                           +---------+----------+       +-----------------------+
                                     | 1
                                     |
                                     v *
+------------------+       +--------------------+       +-----------------------+
|       Item       | 1   * |       Order        | 1   1 |        Invoice        |
+------------------+------>+--------------------+------>+-----------------------+
| id (PK)          |       | id (PK)            |       | id (PK)               |
| name             |       | salesman_name      |       | invoice_no            |
| category         |       | customer_id (FK)   |       | order_id (FK)         |
| base_unit        |       | item_id (FK)       |       | taxable_paise         |
| display_unit     |       | qty_packets        |       | cgst / sgst / igst    |
| conversion_factor|       | unit_price_paise   |       | grand_total_paise     |
| selling_price    |       | status             |       | dispatched (bool)     |
| hsn_code, gst_%  |       +--------------------+       +-----------+-----------+
+--+----+----+-----+                                                | 1
   |    |    |                                                      v *
   |    |    | 1   *       +--------------------+       +-----------------------+
   |    |    +------------>|    StockLedger     |       |        Payment        |
   |    |                  +--------------------+       +-----------------------+
   |    |                  | id (PK)            |       | id (PK)               |
   |    |                  | item_id (FK)       |       | invoice_id (FK)       |
   |    |                  | movement_type      |       | amount_paise          |
   |    |                  | qty_delta_base     |       | mode, created_at      |
   |    |                  | unit_cost_paise    |       +-----------------------+
   |    |                  | ref_type, ref_id   |
   |    |                  +--------------------+
   |    |
   |    | 1   *            +--------------------+       +-----------------------+
   |    +----------------->|     RecipeBOM      |       |     ProductionRun     |
   |                       +--------------------+       +-----------------------+
   |                       | id (PK)            |       | id (PK)               |
   |                       | finished_item_id   |       | finished_item_id (FK) |
   |                       | ingredient_item_id |       | expected_packets      |
   |                       | std_qty_base       |       | actual_good_packets   |
   |                       | expected_yield_pcs |       | damaged_pouches       |
   |                       +--------------------+       | cartons_used          |
   |                                                    | yield_variance_pct    |
   | 1   *                 +--------------------+       | labour_cost_paise     |
   +---------------------->|      Purchase      |       | overhead_cost_paise   |
                           +--------------------+       | cost_per_packet_paise |
                           | id (PK)            |       +-----------------------+
                           | supplier_name      |
                           | item_id (FK)       |
                           | qty_base           |
                           | rate_paise, total  |
                           +--------------------+
```

---

## 3. BOM Consumption, Unit Conversion & Variance Logic

### A. Unit Normalization (Zero Rounding Drift)
* All physical quantities are persisted in **integer base units** (`g` for mass, `ml` for volume, `pcs` for discrete items), while financial values are persisted in **integer paise** (`Rs. 1.00 = 100 paise`).
* Each `Item` stores a `conversion_factor` (`1000` for `kg -> g` and `L -> ml`; `1` for `pcs`). Supervisor inputs in display units (`40 kg`, `10.5 L`) are multiplied by `conversion_factor` before writing to the ledger.

### B. Planned vs. Actual Variance Engine
When a production run is saved, the engine compares actual floor usage and output against `RecipeBOM` standards scaled by `batches`:

$$\text{Consumption Variance \%} = \frac{\text{Actual Issued} - \text{BOM Standard}}{\text{BOM Standard}} \times 100$$

$$\text{Yield Variance \%} = \frac{\text{Actual Good Packets} - \text{Expected Yield}}{\text{Expected Yield}} \times 100$$

* Any deviation beyond the configurable **$\pm 3.0\%$ tolerance** automatically sets a warning flag (`Oil +5.0%`, `Yield -6.0%`) on the run record and surfaces on the Owner dashboard.
* **Packaging Scrap Isolation:** Good pouches (`188`) are logged as `PROD_ISSUE`, while damaged pouches (`6`) are logged separately as `WASTAGE`. Both deduct from pouch inventory (`194` total), ensuring physical stock accuracy while isolating scrap metrics.

---

## 4. Costing, GST Rules & Production Planning

### A. Inventory Valuation & Unit Costing
* **Weighted Average Valuation:** Before deducting ingredients for a production run, the engine computes each material's weighted average rate from all `OPENING` and `PURCHASE` ledger entries (`Flour`: `(100 kg x Rs. 42 + 60 kg x Rs. 45) / 160 kg = Rs. 43.125/kg`).
* **Overhead Allocation & Unit Cost:** Direct batch overheads (`Rs. 1,200` labour + `Rs. 600` gas/power = `Rs. 1,800`) are allocated 100% to the batch's good output (`188` packets):
  $$\text{Cost per Packet} = \frac{\text{Rs. } 4,055.00\text{ (Materials + Packaging incl. Scrap)} + \text{Rs. } 1,800.00\text{ (Overheads)}}{188\text{ packets}} = \text{Rs. } 31.14$$

### B. GST Place-of-Supply Rule & Multi-Pack Extensibility
* **GST Tax Split:** Comparing `Customer.state` against the factory state (`Tamil Nadu`) routes 5% GST into `2.5% CGST + 2.5% SGST` for intra-state orders (`Retailer A`) or `5.0% IGST` for inter-state orders (`Distributor B`).
* **Multi-Pack Extensibility:** Because `RecipeBOM` maps a finished SKU to raw materials via `std_qty_base` and `expected_yield_pcs`, adding a new pack size (e.g., **Murukku 500 g** yielding `80` packets per `40 kg` flour batch) requires only adding a new `Item` row and corresponding `RecipeBOM` rows—requiring zero schema or engine modifications.

### C. Demand-Driven Production Planning & Floor Localization
* **Pending-Order Batch Planner:** The system aggregates unfulfilled demand (`SUBMITTED` and `SHORTAGE_HOLD` orders), subtracts live finished-goods inventory, and computes required production batches:
  $$\text{Recommended Batches} = \left\lceil \frac{\max(0,\ \text{Pending Demand} - \text{Available Stock})}{\text{Expected Batch Yield}} \right\rceil$$
* **Shop-Floor Localization (`EN / தமிழ்`):** The Production Supervisor workspace supports instant language switching between English and Tamil without altering underlying ledger units or audit logs.