# Financial Download Automation Configuration

This setup lets Fulcrum decide automatically:
- what to download,
- from which years,
- how many years,
- and in what source order (BSE/NSE/MCA).

## Files

- Config: `/Users/soumya/Desktop/Projects/fulcrum/config/download_config.toml`
- Planner script: `/Users/soumya/Desktop/Projects/fulcrum/scripts/build_financial_download_plan.py`
- Generated plan: `/Users/soumya/Desktop/Projects/fulcrum/data/processed/financial_download_plan.csv`

## How it decides

1. Defaulters anchor year (`anchor_fy`)
- Default mode uses `fy_before_default`.
- If missing, it uses `default_year - 1`.
- If still missing, it uses `general.default_anchor_fy`.

2. Non-defaulters anchor year
- Default mode is `sector_median_from_defaulters`.
- For each sector, it uses median defaulter anchor year in that sector.
- Sector labels can be remapped with `non_defaulters.sector_aliases`.
- If sector match is missing, it falls back to global median defaulter anchor year.

3. Target years
- `general.lookback_years = 3` means `anchor_fy, anchor_fy-1, anchor_fy-2`.
- Controlled by `general.year_order` (`desc` or `asc`).

4. Document types
- `documents.required` are must-download jobs.
- `documents.optional` are nice-to-have jobs.

5. Source priority
- Listed/public (`CIN` starts with `L` by default): `bse|nse|mca`
- Unlisted/private: `mca`

## Command

```bash
/Users/soumya/Desktop/Projects/fulcrum/.venv/bin/python /Users/soumya/Desktop/Projects/fulcrum/scripts/build_financial_download_plan.py
```

With custom files:

```bash
/Users/soumya/Desktop/Projects/fulcrum/.venv/bin/python /Users/soumya/Desktop/Projects/fulcrum/scripts/build_financial_download_plan.py \
  --config /Users/soumya/Desktop/Projects/fulcrum/config/download_config.toml \
  --defaulters /Users/soumya/Desktop/Projects/fulcrum/data/cibil/wilful_defaulters_50.csv \
  --non-defaulters /Users/soumya/Desktop/Projects/fulcrum/data/cibil/non_defaulters_50.csv \
  --output /Users/soumya/Desktop/Projects/fulcrum/data/processed/financial_download_plan.csv
```

## Output columns (plan CSV)

- `cohort`: `defaulter` or `non_defaulter`
- `company_name`, `cin`, `sector`
- `is_listed`
- `anchor_fy`, `anchor_reason`
- `target_fy`
- `doc_type`
- `required`
- `source_priority`
- `default_year`, `fy_before_default`

Each row is one concrete download job.

## Typical tuning changes

In `/Users/soumya/Desktop/Projects/fulcrum/config/download_config.toml`:

- Increase years from 3 to 5:
  - `general.lookback_years = 5`
- Use fixed years for non-defaulters:
  - `non_defaulters.anchor_mode = "fixed_year"`
  - `non_defaulters.fixed_anchor_fy = 2023`
- Map sector labels before matching:
  - `non_defaulters.sector_aliases."Travel / Hospitality" = "Travel / Aviation / Hospitality"`
- Keep only core financials:
  - edit `documents.required` to just `annual_report`, `balance_sheet`, `profit_and_loss`, `cash_flow`
- Force MCA first:
  - `sources.priority_listed = ["mca", "bse", "nse"]`
