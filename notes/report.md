# Fulcrum Project Report (As of March 5, 2026)

## 1. Current Pipeline Status

Fulcrum is operational end-to-end: data preparation -> feature engineering -> model training -> artifact generation -> API inference -> frontend model/scoring pages.

- Production model: `logistic_regression`
- Production threshold: `0.78`
- Production manifest: `artifacts/models/production_model.json`

## 2. Data and Feature Snapshot

- Raw extracted company-year data: `data/processed/data.csv`
- Engineered dataset: `data/processed/model_features.csv`
  - Rows: `300`
  - Columns: `121`
- Training matrix: `data/processed/training_matrix.csv`
  - Rows: `300`
  - Columns: `106`
  - Companies: `100`
  - Years per company: `3`
  - Label balance: `{0: 150, 1: 150}`

Model input footprint (per trained model bundle):
- Input columns: `62` (`61` numeric + `1` categorical `sector`)
- Transformed columns after preprocessing: `82`
- Sector categories: `21`

## 3. Models Trained

Trained via `scripts/train_models.py`:

1. Logistic Regression
2. Random Forest
3. HistGradientBoosting

Model comparison output: `artifacts/reports/model_leaderboard.csv`

## 4. Model Metrics

### Validation Metrics

| Model | Threshold | PR-AUC | ROC-AUC | Precision | Recall | F1 | Brier |
|---|---:|---:|---:|---:|---:|---:|---:|
| logistic_regression | 0.78 | 0.9278 | 0.9048 | 0.9000 | 0.7500 | 0.8182 | 0.1523 |
| random_forest | 0.48 | 0.8808 | 0.8512 | 0.8333 | 0.8333 | 0.8333 | 0.1538 |
| hist_gradient_boosting | 0.39 | 0.8964 | 0.8810 | 0.8462 | 0.9167 | 0.8800 | 0.1439 |

### Test Metrics

| Model | PR-AUC | ROC-AUC | Precision | Recall | F1 | Brier |
|---|---:|---:|---:|---:|---:|---:|
| logistic_regression | 0.9562 | 0.9583 | 0.9412 | 0.7619 | 0.8421 | 0.0863 |
| random_forest | 0.9590 | 0.9742 | 0.8400 | 1.0000 | 0.9130 | 0.0791 |
| hist_gradient_boosting | 0.9210 | 0.9603 | 0.8400 | 1.0000 | 0.9130 | 0.0803 |

### Confusion Matrices

Validation:
- logistic_regression: `[[19, 2], [6, 18]]`
- random_forest: `[[17, 4], [4, 20]]`
- hist_gradient_boosting: `[[17, 4], [2, 22]]`

Test:
- logistic_regression: `[[23, 1], [5, 16]]`
- random_forest: `[[20, 4], [0, 21]]`
- hist_gradient_boosting: `[[20, 4], [0, 21]]`

Detailed files:
- `artifacts/reports/validation_metrics.json`
- `artifacts/reports/test_metrics.json`

## 5. Production Selection

Current production model is:
- `model_name`: `logistic_regression`
- `model_version`: `v1`
- `feature_list_version`: `v1`
- `threshold_version`: `v1`
- Params: `{ "C": 10.0 }`
- Dataset hash: `fcdf9741fb9c14a65e44dad23efd249f5c7570598f8549267e876584fe4f9078`

Source: `artifacts/models/production_model.json`

## 6. Feature Importance / Model Signals

### Logistic Regression (top absolute coefficients)
Source: `artifacts/reports/logistic_regression_coefficients.csv`

Top contributors include:
- `sector_FMCG / Foods / Agro`
- `capex_effective`
- `debt_to_assets`
- `revenue_volatility_3y`
- `revenue`
- `tax_expense`
- `debt_to_equity`

### Random Forest (top importances)
Source: `artifacts/reports/random_forest_feature_importance.csv`

Top features include:
- `debt_to_assets`
- `tax_expense`
- `interest_coverage`
- `net_profit_margin`
- `roa`
- `debt_to_equity`
- `altman_z_proxy`

## 7. Hybrid Risk Decision Layer

Implemented in:
- `scripts/risk_decision.py`
- `config/risk_rules.yaml`

Scoring output combines:
- ML probability and thresholded class
- Rule-based red flags (critical + trend)
- Final risk band
- Top reasons and support summary

Current rule set:
- Critical rules: `8`
- Trend rules: `5`

Framing used in output:
> "This score estimates how closely the company's financial pattern resembles historical wilful defaulter cases in the training dataset."

## 8. API and Frontend Status

### Backend API (`api/predict.py`)

- `GET /health`
- `GET /models`
- `GET /models/{model_name}`
- `POST /score-company-csv`
- `POST /score-company-json`

### Frontend (Next.js)

- `/` -> landing page
- `/models` -> model registry/details
- `/score` -> CSV upload + scoring output

Proxy routes in frontend:
- `/api/models` -> backend `/models`
- `/api/score-company-csv` -> backend `/score-company-csv`

## 9. Demo Inputs and Observed Behavior

Demo files in `demo/`:
- `demo_high_risk_company_3y.csv` -> High
- `demo_borderline_company_3y.csv` -> Medium
- `demo_low_risk_company_3y.csv` -> Low
- `demo_single_year_company_1y.csv` -> Low + reduced-confidence warning

## 10. Caveats for Presentation

1. Risk band is ML-first.
   - If ML probability exceeds threshold, band is High even when rule flags are low.

2. V1 still shows shortcut-learning risk.
   - Some sparse/category features can act as proxies due to distribution imbalance.

3. Probability calibration is limited.
   - Scores can become very close to `0` or `1` on some inputs.

4. Missingness remains meaningful.
   - Many governance/audit fields are sparse, so imputation warnings are expected.

5. This is decision support, not legal classification.
   - Output indicates pattern similarity, not legal guilt, fraud proof, or definitive wilful-default adjudication.

## 11. Recommended Next Actions (V2)

1. Feature-risk audit for leakage/shortcut features.
2. Rebalance/normalize sector and sparse audit-presence features.
3. Retrain with a cleaned V2 feature policy.
4. Re-evaluate calibration and demo stability post-retraining.
