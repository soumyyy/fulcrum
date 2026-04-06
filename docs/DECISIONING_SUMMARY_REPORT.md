# Decisioning Summary Report

## Executive Summary

- Portfolio scored: **100 companies / 300 company-years**
- Production engine: **hist_gradient_boosting**
- Audit baseline: **logistic_regression**
- High-band latest rows: **63 / 100**
- Urgent-review latest rows: **43 / 100**
- Model disagreements on latest rows: **8 / 100**

## What The Product Is

This is now a usable internal decisioning layer.

- The engine model ranks risk.
- The logistic model acts as a baseline audit check.
- Rule triggers provide support and narrative.
- The final action queue comes from `decision_bucket`, not from raw probability alone.

This is good enough for internal triage, screening, and portfolio review.
It is not yet a forward-looking default-timing model.

## Bucket Summary

| decision_bucket   |   companies |   avg_engine_score |   avg_rule_flags | disagree_rate   |
|:------------------|------------:|-------------------:|-----------------:|:----------------|
| urgent_review     |          43 |              73.63 |             6.3  | 0.0%            |
| monitor           |          24 |              33.36 |             0.54 | 0.0%            |
| watchlist         |          19 |              33.62 |             3.32 | 0.0%            |
| manual_check      |           8 |              43.42 |             2.25 | 100.0%          |
| review            |           6 |              71.98 |             1    | 0.0%            |

## Cohort Summary

| cohort        |   companies |   avg_engine_score | high_band_rate   | urgent_review_rate   |
|:--------------|------------:|-------------------:|:-----------------|:---------------------|
| defaulter     |          50 |              73.34 | 100.0%           | 86.0%                |
| non_defaulter |          50 |              34.36 | 26.0%            | 0.0%                 |

## Sector Hotspots

| sector                          |   companies |   avg_engine_score | urgent_review_rate   |
|:--------------------------------|------------:|-------------------:|:---------------------|
| Oil & Gas / Energy              |           2 |              75.2  | 100.0%               |
| Travel / Aviation / Hospitality |           3 |              63.49 | 100.0%               |
| FMCG / Foods / Agro             |           7 |              74.91 | 85.7%                |
| Infrastructure                  |          17 |              58.87 | 58.8%                |
| Steel & Metals                  |           8 |              54.52 | 50.0%                |
| Media                           |           2 |              54.18 | 50.0%                |
| Logistics                       |           2 |              54.14 | 50.0%                |
| Shipbuilding                    |           2 |              54.11 | 50.0%                |
| NBFC / Leasing                  |           2 |              54.08 | 50.0%                |
| Cement                          |           2 |              53.85 | 50.0%                |
| Textiles                        |           9 |              51.73 | 44.4%                |
| Gems & Jewellery                |          12 |              57.34 | 33.3%                |

## Top Urgent Review Names

| company_name                |   financial_year | sector                      |   engine_score_0_100 |   audit_score_0_100 |   rule_flag_count |   critical_rule_count | top_reasons                                                                                                                                                                                                                             |
|:----------------------------|-----------------:|:----------------------------|---------------------:|--------------------:|------------------:|----------------------:|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Simbhaoli Sugars Ltd        |             2023 | FMCG / Foods / Agro         |                75.22 |               73.76 |                 4 |                     2 | Interest coverage is below 1, suggesting operating earnings may not comfortably cover finance costs. | Net profit margin is negative. | Revenue trend over the available years is negative.                                             |
| REI Agro                    |             2016 | FMCG / Foods / Agro         |                75.22 |               73.87 |                 5 |                     2 | Interest coverage is below 1, suggesting operating earnings may not comfortably cover finance costs. | Net profit margin is negative. | Revenue trend over the available years is negative.                                             |
| Unity Infraprojects         |             2016 | Infrastructure              |                75.22 |               73.87 |                 8 |                     4 | Interest coverage is below 1, suggesting operating earnings may not comfortably cover finance costs. | Debt-to-equity is above 2, indicating elevated leverage. | Operating cash flow is negative despite positive revenue.             |
| IVRCL Limited               |             2016 | Infrastructure              |                75.22 |               73.42 |                 8 |                     4 | Interest coverage is below 1, suggesting operating earnings may not comfortably cover finance costs. | Debt-to-equity is above 2, indicating elevated leverage. | Operating cash flow is negative despite positive revenue.             |
| Visa Steel Limited          |             2021 | Steel & Metals              |                75.22 |               73.84 |                 6 |                     2 | Interest coverage is below 1, suggesting operating earnings may not comfortably cover finance costs. | Net profit margin is negative. | Revenue trend over the available years is negative.                                             |
| Shree Renuka Sugars Limited |             2022 | FMCG / Foods / Agro         |                75.22 |               73.25 |                 3 |                     1 | Debt-to-equity is above 2, indicating elevated leverage. | Operating cash flow trend over the available years is negative. | Borrowings trend over the available years is increasing.                                                   |
| Moser Baer India            |             2016 | Engineering / Manufacturing |                75.22 |               73.87 |                 6 |                     2 | Interest coverage is below 1, suggesting operating earnings may not comfortably cover finance costs. | Net profit margin is negative. | Revenue trend over the available years is negative.                                             |
| Era Infra Engineering       |             2017 | Infrastructure              |                75.22 |               73.86 |                 4 |                     2 | Interest coverage is below 1, suggesting operating earnings may not comfortably cover finance costs. | Net profit margin is negative. | Revenue trend over the available years is negative.                                             |
| Monnet Ispat & Energy Ltd   |             2016 | Steel & Metals              |                75.22 |               73.62 |                 7 |                     3 | Interest coverage is below 1, suggesting operating earnings may not comfortably cover finance costs. | Debt-to-equity is above 2, indicating elevated leverage. | Net profit margin is negative.                                        |
| C Mahendra Exports Limited  |             2015 | Gems & Jewellery            |                75.22 |               73.72 |                 9 |                     4 | Interest coverage is below 1, suggesting operating earnings may not comfortably cover finance costs. | Debt-to-equity is above 2, indicating elevated leverage. | Operating cash flow is negative despite positive revenue.             |
| JVL Agro Industries         |             2018 | FMCG / Foods / Agro         |                75.22 |               73.35 |                 5 |                     2 | Interest coverage is below 1, suggesting operating earnings may not comfortably cover finance costs. | Operating cash flow is negative despite positive revenue. | Revenue trend over the available years is negative.                  |
| Metalyst Forgings           |             2016 | Engineering / Manufacturing |                75.21 |               73.78 |                 8 |                     3 | Interest coverage is below 1, suggesting operating earnings may not comfortably cover finance costs. | Debt-to-equity is above 2, indicating elevated leverage. | Net profit margin is negative.                                        |
| SVOGL Oil Gas and Energy    |             2015 | Oil & Gas / Energy          |                75.21 |               73.87 |                 9 |                     4 | Interest coverage is below 1, suggesting operating earnings may not comfortably cover finance costs. | Debt-to-equity is above 2, indicating elevated leverage. | Operating cash flow is negative despite positive revenue.             |
| ABG Shipyard Ltd            |             2016 | Shipbuilding                |                75.21 |               73.87 |                 8 |                     4 | Interest coverage is below 1, suggesting operating earnings may not comfortably cover finance costs. | Current ratio is below 1, indicating a short-term liquidity deficit. | Operating cash flow is negative despite positive revenue. |
| Surya Pharmaceutical        |             2014 | Pharma                      |                75.21 |               73.87 |                 7 |                     3 | Interest coverage is below 1, suggesting operating earnings may not comfortably cover finance costs. | Current ratio is below 1, indicating a short-term liquidity deficit. | Net profit margin is negative.                            |

## Model Disagreement Cases

| company_name                          |   financial_year | sector           |   engine_score_0_100 |   audit_score_0_100 | engine_risk_band   | audit_risk_band   | decision_bucket   |   imputed_feature_fraction | top_reasons                                                                                                                                                                            |
|:--------------------------------------|-----------------:|:-----------------|---------------------:|--------------------:|:-------------------|:------------------|:------------------|---------------------------:|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Winsome Diamonds and Jewellery        |             2012 | Gems & Jewellery |                74.37 |               38.15 | High               | Medium            | manual_check      |                          0 | Operating cash flow is negative despite positive revenue. | Operating cash flow trend over the available years is negative. | Borrowings trend over the available years is increasing. |
| Elder Pharmaceuticals Ltd             |             2014 | Pharma           |                69.18 |               41.34 | High               | Medium            | manual_check      |                          0 | Current ratio is below 1, indicating a short-term liquidity deficit. | Revenue trend over the available years is negative. | Net profit margin deteriorated materially year over year. |
| Dilip Buildcon Limited                |             2016 | Infrastructure   |                37.54 |               55.33 | High               | High              | manual_check      |                          0 | Debt-to-equity is above 2, indicating elevated leverage. | Borrowings trend over the available years is increasing.                                                                    |
| DLF Limited                           |             2018 | Real Estate      |                33.63 |               44.82 | Medium             | High              | manual_check      |                          0 | Revenue trend over the available years is negative. | Operating cash flow trend over the available years is negative.                                                                  |
| Vaibhav Global Limited                |             2017 | Gems & Jewellery |                33.28 |               61.7  | Medium             | High              | manual_check      |                          0 | Operating cash flow trend over the available years is negative. | Borrowings trend over the available years is increasing.                                                             |
| Senco Gold Limited                    |             2020 | Gems & Jewellery |                33.24 |               53.74 | Medium             | High              | manual_check      |                          0 | Borrowings trend over the available years is increasing.                                                                                                                               |
| IRB Infrastructure Developers Limited |             2016 | Infrastructure   |                33.18 |               59.88 | High               | High              | manual_check      |                          0 | Current ratio is below 1, indicating a short-term liquidity deficit. | Contingent liabilities exceed 50% of net worth. | Borrowings trend over the available years is increasing.      |
| Jindal Steel & Power Limited          |             2017 | Steel & Metals   |                32.9  |               42.34 | High               | High              | manual_check      |                          0 | Interest coverage is below 1, suggesting operating earnings may not comfortably cover finance costs. | Net profit margin is negative.                                                  |

## Lowest-Risk Monitor Names

| company_name                            |   financial_year | sector            |   engine_score_0_100 |   audit_score_0_100 |   rule_flag_count | top_reasons                                              |
|:----------------------------------------|-----------------:|:------------------|---------------------:|--------------------:|------------------:|:---------------------------------------------------------|
| Oil and Natural Gas Corporation Limited |             2017 | Oil & Gas         |                32.91 |               31    |                 1 | Revenue trend over the available years is negative.      |
| Britannia Industries Limited            |             2018 | FMCG / Foods      |                32.84 |               30.95 |                 1 | Borrowings trend over the available years is increasing. |
| Larsen & Toubro Limited                 |             2016 | Infrastructure    |                32.83 |               31.46 |                 1 | Borrowings trend over the available years is increasing. |
| Grasim Industries Limited               |             2017 | Textiles          |                32.83 |               30.95 |                 0 |                                                          |
| Nestle India Limited                    |             2018 | FMCG / Foods      |                32.83 |               30.96 |                 1 | Borrowings trend over the available years is increasing. |
| ITC Limited                             |             2018 | FMCG / Foods      |                32.83 |               30.94 |                 0 |                                                          |
| Hindustan Unilever Limited              |             2018 | FMCG / Foods      |                32.83 |               30.93 |                 0 |                                                          |
| Infosys Limited                         |             2017 | IT / Services     |                32.82 |               30.93 |                 0 |                                                          |
| UltraTech Cement Limited                |             2016 | Cement            |                32.82 |               33.69 |                 1 | Borrowings trend over the available years is increasing. |
| InterGlobe Aviation Limited             |             2018 | Travel / Aviation |                32.82 |               31.06 |                 0 |                                                          |

## Reflection

The product is strongest where all three layers line up:

- engine probability is high
- logistic audit baseline agrees
- rule flags are present

That gives a credible internal action signal.

The current weakness is not feature engineering anymore. The weakness is product tuning:

- the urgent queue is still too broad
- sector-relative interpretation needs tighter use
- thresholding and bucket logic should be tuned against how you want analysts to work

## Recommended Next Moves

1. Reduce queue size by tightening `urgent_review` criteria.
2. Review the disagreement cases manually and decide whether disagreement should force `manual_check` more often.
3. Decide whether your operating unit works by:
   - bucket first, then score
   - or score first, then analyst override
4. Add a presentation layer next:
   - one portfolio dashboard
   - one company detail view
5. Only after that, revisit more data collection or label redesign.

## Operating Recommendation

Use these outputs in this order:

1. `/Users/soumya/Desktop/Projects/fulcrum/data/processed/decisioning_output_latest.csv`
2. `/Users/soumya/Desktop/Projects/fulcrum/data/processed/decisioning_output_years.csv`
3. this report for portfolio-level review

For actual workflow:

- `urgent_review`: immediate analyst review
- `review`: second queue
- `watchlist`: monitor
- `manual_check`: inspect disagreement / missingness
- `monitor`: no active action
