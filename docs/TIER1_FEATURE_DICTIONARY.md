# Tier 1 Feature Dictionary

This is the baseline feature set to start model development on the current dataset.

Tier 1 is designed for:
- rule-based scorecard
- logistic regression
- tree models
- anomaly detection
- clustering

All amount fields in the source dataset are in `Rs crore`. Ratios are unitless.

## Build Rules

- Denominator guard: if denominator is missing or `0`, return null.
- Positive denominator guard: if denominator is missing, `0`, or negative, return null.
- Log features: only compute when the raw value is strictly positive.
- YoY growth uses normalized change:
  - `(current - previous) / abs(previous)`
  - if previous is missing or `0`, return null.

## Tier 1 Features

| Feature | Formula | Guard | Purpose | Primary Models |
|---|---|---|---|---|
| `debt_to_equity` | `total_borrowings / total_equity` | positive denominator | leverage stress | all |
| `debt_to_assets` | `total_borrowings / total_assets` | denominator non-zero | leverage intensity | all |
| `ebitda_margin` | `ebitda / revenue` | denominator non-zero | operating profitability | all |
| `pat_margin` | `pat / revenue` | denominator non-zero | bottom-line profitability | all |
| `roa` | `pat / total_assets` | denominator non-zero | return on asset base | all |
| `roe` | `pat / total_equity` | positive denominator | equity return quality | all |
| `ebitda_to_interest` | `ebitda / interest_expense` | positive denominator | debt-servicing capacity | scorecard, logistic, tree |
| `cfo_to_assets` | `cfo / total_assets` | denominator non-zero | cash generation against asset base | all |
| `cfo_to_debt` | `cfo / total_borrowings` | denominator non-zero | cash debt coverage | all |
| `cfo_to_ebitda` | `cfo / ebitda` | denominator non-zero | earnings quality / cash conversion | scorecard, logistic, tree, anomaly |
| `retained_earnings_to_assets` | `retained_earnings / total_assets` | denominator non-zero | balance-sheet resilience | all |
| `net_cash_change_to_assets` | `net_cash_change / total_assets` | denominator non-zero | overall liquidity pressure | all |
| `log_total_assets` | `ln(total_assets)` | `total_assets > 0` | size normalization | logistic, tree, anomaly, clustering |
| `log_revenue` | `ln(revenue)` | `revenue > 0` | size normalization | logistic, tree, anomaly, clustering |
| `revenue_growth_yoy` | `(revenue_t - revenue_t-1) / abs(revenue_t-1)` | prior present and non-zero | top-line deterioration / expansion | all |
| `debt_growth_yoy` | `(total_borrowings_t - total_borrowings_t-1) / abs(total_borrowings_t-1)` | prior present and non-zero | leverage acceleration | all |
| `cfo_growth_yoy` | `(cfo_t - cfo_t-1) / abs(cfo_t-1)` | prior present and non-zero | cash-flow deterioration / recovery | all |
| `asset_growth_yoy` | `(total_assets_t - total_assets_t-1) / abs(total_assets_t-1)` | prior present and non-zero | balance-sheet expansion / contraction | logistic, tree, anomaly, clustering |

## Source Mapping

| Tier 1 Feature | Upstream columns |
|---|---|
| `debt_to_equity` | `total_borrowings`, `total_equity` |
| `debt_to_assets` | `total_borrowings`, `total_assets` |
| `ebitda_margin` | `ebitda`, `revenue` |
| `pat_margin` | `pat`, `revenue` |
| `roa` | `pat`, `total_assets` |
| `roe` | `pat`, `total_equity` |
| `ebitda_to_interest` | `ebitda`, `interest_expense` |
| `cfo_to_assets` | `cfo`, `total_assets` |
| `cfo_to_debt` | `cfo`, `total_borrowings` |
| `cfo_to_ebitda` | `cfo`, `ebitda` |
| `retained_earnings_to_assets` | `retained_earnings`, `total_assets` |
| `net_cash_change_to_assets` | `net_cash_change`, `total_assets` |
| `log_total_assets` | `total_assets` |
| `log_revenue` | `revenue` |
| `revenue_growth_yoy` | `revenue`, `financial_year`, `company_name` |
| `debt_growth_yoy` | `total_borrowings`, `financial_year`, `company_name` |
| `cfo_growth_yoy` | `cfo`, `financial_year`, `company_name` |
| `asset_growth_yoy` | `total_assets`, `financial_year`, `company_name` |

## Model-Specific Usage

### Rule-Based Scorecard
- `debt_to_equity`
- `debt_to_assets`
- `ebitda_margin`
- `pat_margin`
- `roa`
- `roe`
- `ebitda_to_interest`
- `cfo_to_assets`
- `cfo_to_debt`
- `cfo_to_ebitda`
- `retained_earnings_to_assets`
- `net_cash_change_to_assets`
- `revenue_growth_yoy`
- `debt_growth_yoy`
- `cfo_growth_yoy`

### Logistic Regression
- `debt_to_equity`
- `debt_to_assets`
- `ebitda_margin`
- `pat_margin`
- `roa`
- `roe`
- `ebitda_to_interest`
- `cfo_to_assets`
- `cfo_to_debt`
- `cfo_to_ebitda`
- `retained_earnings_to_assets`
- `net_cash_change_to_assets`
- `log_total_assets`
- `log_revenue`
- `revenue_growth_yoy`
- `debt_growth_yoy`
- `cfo_growth_yoy`
- `asset_growth_yoy`

### Tree Models
- all Tier 1 features

### Isolation Forest
- all Tier 1 features

### KMeans Clustering
- `debt_to_assets`
- `ebitda_margin`
- `pat_margin`
- `roa`
- `cfo_to_assets`
- `retained_earnings_to_assets`
- `log_total_assets`
- `log_revenue`
- `revenue_growth_yoy`
- `debt_growth_yoy`
- `asset_growth_yoy`

## Pipeline Mapping

- feature builder: `/Users/soumya/Desktop/Projects/fulcrum/scripts/build_model_features.py`
- Tier 1 training config: `/Users/soumya/Desktop/Projects/fulcrum/config/model_train_config_tier1.yaml`

The Tier 1 feature names in this file match the engineered column names produced by the feature builder.
