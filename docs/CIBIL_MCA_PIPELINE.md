# CIBIL → CIN → MCA Pipeline

This pipeline takes a company list (e.g. from TransUnion CIBIL export) and fetches each company’s report from the MCA portal using its CIN (Corporate Identification Number).

**Initial scope:** 50 wilful defaulters (from RBI list) + 50 non-defaulters (from CIBIL or MCA+exclusion). Same pipeline is used for both cohorts once we have company name + CIN.

## Flow

1. **CIBIL data** – CSV with at least company name; CIN column optional.
2. **CIN** – If present, used as-is (normalized). If missing, those rows are skipped (CIN resolution can be added later).
3. **MCA report** – For each row with CIN, the script opens the MCA “View Public Documents” page, searches by CIN, and (in later steps) lists/downloads documents (e.g. Annual Returns and Balance Sheet / Form AOC-4).

## Input CSV format

- **company_name** (required): any column that maps to company name, e.g.  
  `Company Name`, `Borrower Name`, `Name of Borrower`, `Name`
- **cin** (optional): 21-character Corporate Identification Number, e.g.  
  `L27100MH1995PLC084207`

If your CIBIL export uses different headers, use:

- `--company-column "Borrower Name"`
- `--cin-column "Company Registration Number"`

Or add aliases in `scripts/cibil_loader.py` (`COLUMN_ALIASES`).

## Setup

```bash
# From project root
pip install -r requirements.txt
playwright install chromium
```

## Commands

**1. Normalize and inspect CIBIL CSV**

```bash
python scripts/cibil_loader.py data/cibil/sample_companies.csv -o data/cibil/normalized.csv
```

**2. Pipeline status (how many CINs done vs pending)**

```bash
python scripts/cibil_mca_pipeline.py status --input data/cibil/companies.csv
```

**3. Run pipeline (fetch MCA for each CIN)**

```bash
# Default input: data/cibil/companies.csv
python scripts/cibil_mca_pipeline.py run --input data/cibil/companies.csv

# Process only 5 CINs (e.g. for testing)
python scripts/cibil_mca_pipeline.py run --input data/cibil/companies.csv --limit 5
```

- Progress is checkpointed in `data/mca/pipeline_checkpoint.csv`. Re-run to resume.
- MCA requires CAPTCHA; run **without** `--headless` so you can solve it when the browser pauses.
- Reports and debug artifacts go under `data/mca/reports/` (and `_debug/` for screenshots/HTML).

## File layout

| Path | Purpose |
|------|--------|
| `data/cibil/companies.csv` | Your CIBIL/company list (create from export) |
| `data/cibil/sample_companies.csv` | Example CSV with company_name + cin |
| `data/mca/pipeline_checkpoint.csv` | Checkpoint: CIN → status (success/error) |
| `data/mca/reports/<CIN>/` | Downloaded MCA documents and `_debug/` (screenshots/HTML) |

## MCA portal notes

- **View Public Documents**: search by Company Registration Number (CIN) and ROC.
- **Viewing** is free; **downloading** costs **₹100 per company** (up to 5 docs, 3-hour window after payment). See **[MCA alternatives and workarounds](MCA_ALTERNATIVES_AND_WORKAROUNDS.md)** for free options (BSE/NSE for listed companies, Screener.in, etc.).
- CAPTCHA is required on search; rate limits ~100–150 requests/hour per IP (script uses delays).
- Document categories include “Annual Returns and Balance Sheet eForms” (Form AOC-4); document listing and download automation can be extended in `scripts/mca_fetcher.py`.

## Next steps

- **CIN resolution**: If CIBIL export has no CIN, add a step to search MCA by company name and get CIN (same portal, different flow).
- **Document download**: In `mca_fetcher.py`, after search, select category “Annual Returns and Balance Sheet”, choose year(s), and download PDFs to `data/mca/reports/{cin}/`.
