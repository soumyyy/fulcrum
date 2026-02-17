# CIBIL / company list data

## Sector-matched 50 + 50 design

| Sector | Defaulters (50) | Non-defaulters (50) |
|--------|------------------|----------------------|
| Gems & Jewellery | 6 | 6 (Titan, Kalyan, Senco, TBZ, Rajesh Exports, Vaibhav Global) |
| Steel & Metals | 4 | 4 (Tata Steel, JSW Steel, SAIL, JSPL) |
| Infrastructure / Construction | 7 | 7 (L&T, NCC, IRB, KEC, Kalpataru, PNC, Dilip Buildcon) |
| FMCG / Foods / Agro | 6 | 6 (ITC, Nestle, Britannia, HUL, Dabur, Marico) |
| Textiles | 4 | 4 (Trident, Welspun, Raymond, Grasim) |
| Pharma | 2 | 2 (Sun Pharma, Dr Reddy's) |
| Travel / Aviation / Hospitality | 3 | 3 (InterGlobe, Indian Hotels, Lemon Tree) |
| Cement | 1 | 1 (UltraTech) |
| Oil & Gas / Energy | 1 | 1 (ONGC) |
| Logistics | 1 | 1 (Blue Dart) |
| Real Estate | 1 | 1 (DLF) |
| NBFC / Leasing | 1 | 1 (Bajaj Finance) |
| Media | 1 | 1 (HT Media) |
| Engineering / Manufacturing | 8 | 8 (ABB, Siemens, BHEL, Thermax, Carborundum, SKF, Timken, Schaeffler) |
| Shipbuilding | 1 | 1 (Cochin Shipyard) |
| Mining | 1 | 1 (Coal India) |
| IT / Services / Export | 2 | 2 (Infosys, Tata Elxsi) |

Non-defaulters are established listed companies (or PSUs) with no wilful-defaulter classification; chosen to mirror the defaulter list sector-wise for a balanced case–control comparison.

---

## wilful_defaulters_50.csv

**50 wilful defaulters** for the Fulcrum project. Source: **RBI top-100 list** (RTI response to Indian Express), as on **June 30, 2024**. Columns:

- **company_name** – Borrower name (as in RBI list)
- **cin** – Empty; resolve via MCA search or entity-resolution step
- **amount_crore** – Amount owed (Rs crore)
- **source** – Citation

**Next step:** Resolve CIN using the CIN resolver script (searches MCA "Find CIN" by company name; you solve CAPTCHA when prompted). Then run the CIBIL→CIN→MCA pipeline to fetch MCA reports.

---

## non_defaulters_50.csv

**50 non-defaulters (control group)** for the Fulcrum project. Sector-matched to the defaulter list so the model compares like-with-like. All are established listed companies (or PSUs) with no wilful-defaulter classification. Columns:

- **company_name** – Borrower name
- **cin** – Empty; resolve via MCA search
- **sector** – Sector (matches defaulter sectors)
- **notes** – Brief note (e.g. Tata Group, PSU, listed)

**Usage:** Same as defaulters – resolve CIN, then run the CIBIL→CIN→MCA pipeline.

---

## Step 1: Resolve CIN

Use the CIN resolver to fill the `cin` column by searching MCA "Find CIN" by company name. **Run with browser visible** so you can solve CAPTCHA when prompted (once per company). Checkpoint lets you resume.

```bash
# Defaulters (run in batches with --limit if needed)
python scripts/cin_resolver.py -i data/cibil/wilful_defaulters_50.csv -o data/cibil/wilful_defaulters_50_with_cin.csv

# Non-defaulters
python scripts/cin_resolver.py -i data/cibil/non_defaulters_50.csv -o data/cibil/non_defaulters_50_with_cin.csv

# Test with 2–3 companies first
python scripts/cin_resolver.py -i data/cibil/wilful_defaulters_50.csv -o data/cibil/wilful_defaulters_50_with_cin.csv --limit 3
```

Checkpoint file: `data/mca/cin_resolver_checkpoint.csv` (company_name → cin). Re-run to resume; already-resolved names are skipped.

## Step 2: Fetch MCA reports

After CIN is filled (use the `*_with_cin.csv` files):

```bash
python scripts/cibil_mca_pipeline.py run --input data/cibil/wilful_defaulters_50_with_cin.csv
python scripts/cibil_mca_pipeline.py run --input data/cibil/non_defaulters_50_with_cin.csv
```

## Other commands

```bash
# Normalize / inspect
python scripts/cibil_loader.py data/cibil/wilful_defaulters_50.csv -o data/cibil/normalized_defaulters.csv
python scripts/cibil_loader.py data/cibil/non_defaulters_50.csv -o data/cibil/normalized_non_defaulters.csv
```
