# Demo Company Input Rules for `/score-company-csv`

This guide defines how to create a demo CSV for the `POST /score-company-csv` endpoint.

The endpoint accepts **one company per upload**, with **1 to 3 rows** representing different financial years for that same company.

## Core rules

1. The CSV must contain data for **only one CIN**.
2. Each row must represent a **different `financial_year`**.
3. Do not repeat the same `(cin, financial_year)` combination.
4. Use **numeric values only** for financial fields.
5. `company_name`, `cin`, and `sector` cannot be blank.
6. If `ebitda` is not provided, then all of these must be present:
   - `pat`
   - `interest_expense`
   - `tax_expense`
   - `depreciation`

## Minimum required columns

These columns must exist in the CSV:

- `company_name`
- `cin`
- `financial_year`
- `sector`
- `revenue`
- `pat`
- `interest_expense`
- `tax_expense`
- `total_equity`
- `total_borrowings`
- `total_assets`
- `cfo`

## Optional but recommended columns

These improve the quality of the score and reduce imputation:

- `depreciation`
- `ebitda`
- `current_assets`
- `current_liabilities`
- `cash_and_equivalents`
- `inventory`
- `receivables`
- `retained_earnings`
- `cfi`
- `cff`
- `net_cash_change`
- `capex`
- `going_concern_uncertainty`
- `emphasis_of_matter`
- `fraud_reported`
- `related_party_transactions_amount`
- `contingent_liabilities_amount`
- `rpt_count`
- `pending_legal_cases_count`
- `promoter_holding_pct`
- `cohort`
- `opinion_type`
- `auditor_name`

## Best practice for demos

For the most convincing demo:

1. Use **3 years** for the same company so the system can compute trend features.
2. Choose a `sector` that already exists in the training data, for example:
   - `Steel & Metals`
   - `Infrastructure`
   - `Engineering / Manufacturing`
   - `Gems & Jewellery`
   - `FMCG / Foods / Agro`
3. Keep the numbers internally consistent:
   - `total_assets` should usually be greater than `total_equity`
   - `total_borrowings` should not be unrealistically larger than `total_assets`
   - `current_assets` and `current_liabilities` should be sensible if you want liquidity ratios
4. If you want a **high-risk** demo outcome, use patterns such as:
   - low or negative `pat`
   - negative `cfo`
   - rising `total_borrowings`
   - low `current_ratio` (`current_assets < current_liabilities`)
   - high `debt_to_equity` (large borrowings, weak equity)
5. If you want a **low-risk** demo outcome, use patterns such as:
   - positive and stable `pat`
   - positive `cfo`
   - moderate borrowings
   - healthy liquidity

## One-year vs three-year demos

### One-year demo

- Valid for the API.
- Simpler to prepare.
- The model will still score it.
- The response will include a warning that temporal trend features were unavailable.

### Three-year demo

- Preferred for presentations.
- Allows year-over-year and 3-year trend calculations.
- Produces a stronger explanation and more realistic output.

## Example CSV header

```csv
company_name,cin,financial_year,sector,revenue,pat,interest_expense,tax_expense,total_equity,total_borrowings,total_assets,cfo,depreciation,ebitda,current_assets,current_liabilities,cash_and_equivalents,inventory,receivables,retained_earnings,cfi,cff,net_cash_change,capex,going_concern_uncertainty,emphasis_of_matter,fraud_reported,related_party_transactions_amount,contingent_liabilities_amount,rpt_count,pending_legal_cases_count,promoter_holding_pct,cohort,opinion_type,auditor_name
```

## Minimal 3-row example structure

```csv
company_name,cin,financial_year,sector,revenue,pat,interest_expense,tax_expense,total_equity,total_borrowings,total_assets,cfo,depreciation
Demo Manufacturing Ltd,L12345MH2015PLC123456,2021,Engineering / Manufacturing,1200,85,40,20,500,300,1100,140,35
Demo Manufacturing Ltd,L12345MH2015PLC123456,2022,Engineering / Manufacturing,1325,92,42,22,560,320,1180,155,37
Demo Manufacturing Ltd,L12345MH2015PLC123456,2023,Engineering / Manufacturing,1450,105,44,24,630,335,1260,175,39
```

## Common mistakes that will fail validation

- Uploading multiple companies in one `/score-company-csv` request
- Blank `company_name`, `cin`, or `sector`
- Text like `N/A`, `unknown`, or `--` in numeric columns
- Duplicate financial years for the same company
- Missing required columns
- Omitting both `ebitda` and `depreciation` when EBITDA cannot be derived

## Recommended demo flow

1. Create a **3-row CSV** for one company.
2. Upload it to `/score-company-csv` from Swagger (`/docs`) or Postman.
3. Show:
   - `ml_probability`
   - `risk_band`
   - `rule_flags_triggered`
   - `top_reasons`
   - `support_summary`
4. Explain that the score reflects similarity to historical wilful-defaulter patterns, not a legal determination.
