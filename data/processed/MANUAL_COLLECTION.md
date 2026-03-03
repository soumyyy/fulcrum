# Manual feature data collection

Start with **one company, one financial year**. Fill one row in `manual_feature_input_template.csv` from Moneycontrol + annual report.

---

## 1. Pick company + year

- **Defaulters:** Use `data/cibil/wilful_defaulters_50.csv`. Pick a company; use **fy_before_default** as the financial year (e.g. Gitanjali Gems → FY **2017**).
- **Non-defaulters:** Use `data/cibil/non_defaulters_50.csv`. Pick a company; use a year you want (e.g. **2022** or **2023** for recent data).

Example: **Gitanjali Gems Limited**, CIN `L36911MH1986PLC040689`, **FY 2017** (financial_year = 2017), cohort = defaulter, sector = Gems & Jewellery.

---

## 2. Fill from Moneycontrol

1. Go to Moneycontrol → search company name (e.g. "Gitanjali Gems" or use BSE/NSE symbol if you know it).
2. Open **Company Info** / **Financials**.
3. Select **standalone** (prefer over consolidated) and the **financial year** (e.g. Mar 2017 for FY 2016–17 → financial_year = **2017**).
4. Fill these (amounts in **Rs crore**):

| Column | Where on Moneycontrol |
|--------|------------------------|
| revenue | P&L – Revenue / Total Income from operations |
| pat | P&L – Net Profit / PAT |
| interest_expense | P&L – Finance costs / Interest |
| depreciation | P&L – Depreciation and amortisation |
| tax_expense | P&L – Tax expense / Provision for tax |
| ebitda | P&L – EBITDA (or leave blank; we can derive) |
| total_equity | Balance Sheet – Total equity / Net worth / Shareholders' funds |
| total_borrowings | Balance Sheet – Borrowings / Total debt |
| current_assets | Balance Sheet – Current assets |
| current_liabilities | Balance Sheet – Current liabilities |
| total_assets | Balance Sheet – Total assets |
| cash_and_equivalents | Balance Sheet – Cash and cash equivalents |
| inventory | Balance Sheet – Inventories |
| receivables | Balance Sheet – Trade receivables / Sundry debtors |
| retained_earnings | Balance Sheet – Retained earnings / Reserves and surplus |
| cfo | Cash Flow – Net cash from operating activities |
| cfi | Cash Flow – Net cash from investing activities |
| cff | Cash Flow – Net cash from financing activities |
| net_cash_change | Cash Flow – Net increase/decrease in cash |
| capex | Cash Flow – Purchase of fixed assets (or leave blank; we can derive from CFI) |

Leave blank if not found; use **financial_year** as the year ending March (e.g. 2017 = FY 2016–17).

---

## 3. Fill from annual report PDF

1. Get PDF: Moneycontrol company page → **Annual Report** link (BSE/NSE or company site).
2. Open the PDF for the **same financial year** (e.g. FY 2016–17 for financial_year = 2017).

**Auditor's report**

| Column | What to extract |
|--------|-----------------|
| opinion_type | One of: unqualified, qualified, adverse, disclaimer |
| going_concern_uncertainty | 1 if "material uncertainty" about going concern; else 0 |
| emphasis_of_matter | 1 if "Emphasis of Matter" paragraph present; else 0 |
| fraud_reported | 1 if fraud or reporting to regulators mentioned; else 0 |
| auditor_name | Name of auditor/firm (for auditor_changed later; e.g. "XYZ & Co.") |

**Notes to accounts**

| Column | What to extract |
|--------|-----------------|
| related_party_transactions_amount | RPT note – total or key amount (Rs crore); blank if none |
| contingent_liabilities_amount | Contingent liabilities note – total (Rs crore); blank if none |
| rpt_count | Number of RPTs if disclosed; else blank |
| pending_legal_cases_count | From contingent/litigation note – count if disclosed; else blank |

**Shareholding pattern**

| Column | What to extract |
|--------|-----------------|
| promoter_holding_pct | Promoter shareholding % (e.g. 45.2) |

---

## 4. Identifiers (first columns)

Fill from your cohort CSV:

- **company_name** – exact name (e.g. Gitanjali Gems Limited)
- **cin** – from cohort CSV
- **financial_year** – year ending March (e.g. 2017)
- **cohort** – defaulter or non_defaulter
- **sector** – from cohort CSV (e.g. Gems & Jewellery)

---

## 5. Save and repeat

- Save one row per company-year in `manual_feature_input_template.csv` (or copy the template and rename to e.g. `manual_collected.csv`).
- Add more rows as you collect more company-years.
- Ratios (current_ratio, debt_to_equity, etc.) and temporal/composite features will be **computed later** from this raw input; you only fill the raw numbers and flags above.

---

## Quick checklist (one company, one year)

- [ ] Company + year chosen (from wilful_defaulters_50 or non_defaulters_50)
- [ ] Moneycontrol: P&L (revenue, pat, interest, depreciation, tax, ebitda)
- [ ] Moneycontrol: Balance Sheet (equity, borrowings, current assets/liabilities, total assets, cash, inventory, receivables, retained_earnings)
- [ ] Moneycontrol: Cash Flow (cfo, cfi, cff, net_cash_change, capex)
- [ ] Annual report: Auditor's report (opinion_type, going_concern, emphasis_of_matter, fraud_reported, auditor_name)
- [ ] Annual report: Notes (RPT amount, contingent amount, rpt_count, pending_legal_cases_count)
- [ ] Annual report: Shareholding (promoter_holding_pct)
- [ ] One row written in template CSV
