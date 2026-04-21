# Fulcrum — Deep Context Analysis

> **Purpose of this document.** A single, opinionated read of the whole project so that any new contributor (or future Claude session) can get from zero to "I understand what this is, how it hangs together, and where the sharp edges are" in one pass. Sourced from a direct walk of the repo on 2026-04-21.

---

## 1. One-paragraph summary

Fulcrum is an **AI-powered credit-risk analyst** for the Indian market. A user uploads an annual-report PDF in the browser; the backend uses Gemini to extract ~25 financial line items, normalizes them to INR crore, computes ~10 Tier-1A financial ratios, runs **two ML models in parallel** (a primary "engine" and an independent "audit" benchmark), writes a grounded LLM memo, and streams the whole thing back to a live report page via Server-Sent Events. It is a Capstone project (NMIMS Sem 8) that behaves like a production demo: end-to-end working pipeline, file-backed job store (no DB), trained on a real 100-company cohort (50 wilful defaulters + 50 controls × 3 FYs).

---

## 2. The product: what the user actually sees

| Route | What it is | Backing data |
|---|---|---|
| [/](frontend/app/page.tsx) | Landing page | static |
| [/fulcrum](frontend/app/fulcrum/page.tsx) | **Model-diagnostics dashboard** over the 100-company historical universe — score distribution, bucket breakdown, sector heat, cohort separation, model-agreement stats. This is a *calibration lens*, not a scoring surface. | `/decisioning/*` APIs |
| [/fulcrum/report/new](frontend/app/fulcrum/report/new/page.tsx) | PDF upload page with a slide-in history sidebar | `POST /reports/upload`, `GET /reports` |
| [/fulcrum/report/[jobId]/processing](frontend/app/fulcrum/report/[jobId]/processing/page.tsx) | 10-step "thinking UI" that streams live progress as each backend stage fires | SSE `/reports/{id}/events` |
| [/fulcrum/report/[jobId]](frontend/app/fulcrum/report/[jobId]/page.tsx) | Full report: company overview, analyst memo, ratio appendix, model decision, financial snapshot, validation panel. Print-friendly layout. | SSE + `/reports/{id}` final payload |
| [/models](frontend/app/models/) | Registry of trained model artifacts with metrics | `GET /models` |
| [/score](frontend/app/score/) | Legacy batch scoring from feature-vector CSV | `POST /score-company-csv` |

Distinction worth internalizing: `/fulcrum` is the **cohort dashboard** (historical, static, calibration). `/fulcrum/report/*` is the **live scoring flow** for a single new PDF.

---

## 3. System architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Browser (Next.js 16 · React 19 · Tailwind v4)                      │
│    frontend/app/...                                                 │
└──────────────┬──────────────────────────────────────────────────────┘
               │  /api/*   (Next.js server routes — thin proxies)
               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  FastAPI backend  (api/predict.py, port 8000)                       │
│    • /reports/*         — upload, status, SSE events, result        │
│    • /decisioning/*     — portfolio summary / company list          │
│    • /models, /models/{name}                                        │
│    • /score-company-*   — legacy feature-vector scoring             │
└──────┬──────────────────────────────┬───────────────────────────────┘
       │                              │
       ▼                              ▼
┌──────────────────────┐   ┌──────────────────────────────────────────┐
│ scripts/             │   │ artifacts/                               │
│  report_job_runner   │   │  models/*.joblib (engine + audit)        │
│  gemini_report_...   │   │  reports/*.json,*.csv (metrics, leader.) │
│  scoring_utils       │   │                                          │
│  risk_decision       │   └──────────────────────────────────────────┘
│  train_models (off.) │
└──────────────────────┘              ┌──────────────────────────────┐
       │                              │ data/                        │
       ▼                              │  processed/*.csv (cohort,    │
┌──────────────────────┐              │    training matrices, etc.)  │
│ Gemini Files API     │              │  cibil/ (raw defaulter list) │
│ gemini-2.5-flash     │              │  report_jobs/{id}/ (runtime) │
└──────────────────────┘              └──────────────────────────────┘
```

### Request flow for a new report

```
Browser → POST /api/reports/upload (Next.js proxy)
        → POST /reports/upload     (FastAPI)
        → create data/report_jobs/{job_id}/{job.json, upload.pdf}
        → schedule background task run_report_job()

Browser → GET /api/reports/{jobId}/events (SSE)
        → streams status / progress / section.complete / job.complete

Background task (scripts/report_job_runner.py):
  1. Upload PDF to Gemini Files API
  2. Extract ~25 fields with gemini-2.5-flash  (scripts/gemini_report_extractor.py)
  3. Validate + normalize monetary units (crore / lakh / million / thousand → crore)
  4. Compute Tier-1A ratios
  5. Score with engine + audit models (scoring_utils.score_single_company)
  6. LLM synthesis of analyst sections → emit section.complete per section
  7. Write result.json → emit job.complete
```

The 10 UI steps in the processing page are a front-loaded re-presentation of 7 backend stages — see [Readme.md:100-115](Readme.md#L100-L115) for the mapping.

---

## 4. Data & ML layer

### 4.1 The cohort

- **100 companies**: 50 wilful defaulters (from RBI/CIBIL list) + 50 non-defaulter controls.
- **3 financial years per company** → **300 rows** in the feature table.
- Raw sources: Moneycontrol (P&L / BS / CFS) + annual-report PDFs. See [docs/DATA_SOURCES_WILFUL_DEFAULTERS.md](docs/DATA_SOURCES_WILFUL_DEFAULTERS.md) and [docs/CIBIL_MCA_PIPELINE.md](docs/CIBIL_MCA_PIPELINE.md).
- Cohort seeds in [data/cibil/](data/cibil/): `wilful_defaulters_50.csv`, `non_defaulters_50.csv`, `normalized.csv`.

### 4.2 Feature engineering

Two feature spec files coexist:

- [config/feature_spec.yaml](config/feature_spec.yaml) — the **full** 81-feature academic spec (P&L, BS, CF, liquidity / leverage / profitability / efficiency ratios, 28 temporal YoY/trend/volatility features, auditor flags, notes, shareholding, Altman Z, Beneish M). Aspirational / reference.
- [config/model_train_config_tier1a.yaml](config/model_train_config_tier1a.yaml) — the **actual** feature set currently in production. Only **10 Tier-1A ratios**:

  ```
  debt_to_assets, ebitda_margin, pat_margin, roa,
  retained_earnings_to_assets, cfo_to_assets, cfo_to_ebitda,
  net_cash_change_to_assets, log_total_assets, log_revenue
  ```

  Plus `sector` as categorical. See [docs/TIER1_FEATURE_DICTIONARY.md](docs/TIER1_FEATURE_DICTIONARY.md) for definitions and guards (denominator guards, log-positivity, YoY normalization).

**Why the gap?** `feature_spec.yaml` describes what *could* be extracted; `tier1a` is what the small cohort supports without shortcut learning. The gap is intentional — `notes/report.md` flags shortcut-learning risk as the #1 V2 item.

### 4.3 Training pipeline

[scripts/train_models.py](scripts/train_models.py) (driven by `model_train_config_tier1a.yaml`):

- Split: 70 train / 15 validation / 15 test **companies** (not rows — splits are *grouped* by company to avoid leakage across financial years of the same firm).
- Numeric imputation: median. Correlation pruning at 0.90.
- Calibration: sigmoid (Platt).
- 5-fold grouped CV for stability estimate.
- Threshold search: sweep `[0.10, 0.90]` at step `0.01`, pick threshold that hits `target_recall=0.75`.
- Four models trained: `logistic_regression`, `random_forest`, `extra_trees`, `hist_gradient_boosting`.

Outputs land in [artifacts/models/](artifacts/models/) and [artifacts/reports/](artifacts/reports/).

### 4.4 Production model selection

[artifacts/models/production_model.json](artifacts/models/production_model.json) pins the current engine:

```json
{
  "model_name": "hist_gradient_boosting",
  "model_version": "tier1a_v1",
  "params": { "learning_rate": 0.05, "max_depth": 5, "max_iter": 200, "min_samples_leaf": 10 },
  "calibration_method": "sigmoid"
}
```

**Two-model design at inference time** (see `_decisioning_summary` in [api/predict.py:210-212](api/predict.py#L210)):

| Role | Model | Purpose |
|---|---|---|
| Engine (primary) | `hist_gradient_boosting` | Produces the 0–100 score and decision bucket |
| Audit (benchmark) | `logistic_regression` | Independent cross-check; disagreement triggers `manual_check` |

`notes/report.md` was written when `logistic_regression` was production — the active pin has since flipped to HGB. Confirm via `production_model.json`, not notes.

### 4.5 Decision buckets

| Bucket | Meaning |
|---|---|
| `urgent_review` | Both models flag high risk |
| `review` | Engine flags high risk |
| `manual_check` | Models disagree / mixed signal |
| `watchlist` | Low risk but rule flags present |
| `monitor` | Clean |

### 4.6 Hybrid rule layer

[scripts/risk_decision.py](scripts/risk_decision.py) + [config/risk_rules.yaml](config/risk_rules.yaml): on top of ML probability, 8 **critical rules** (interest coverage < 1, D/E > 2, current ratio < 1, negative CFO with positive revenue, negative margin, qualified audit, going concern, contingent > 50% net worth) and 5 **trend rules** (declining revenue/CFO, rising borrowings, leverage spike, margin drop). Rule hits become the "top drivers" in the analyst memo.

---

## 5. Backend surface area

All served from [api/predict.py](api/predict.py) on `127.0.0.1:8000`:

### Report pipeline
- `POST /reports/upload` — multipart PDF → creates job, returns `job_id` + `events_url`
- `GET  /reports` — paginated job list with summaries
- `GET  /reports/{job_id}/status` — progress %, current stage
- `GET  /reports/{job_id}/events` — **SSE stream** (status / progress / section / complete)
- `GET  /reports/{job_id}` — final completed result (after `job.complete`)

### Decisioning (historical universe — powers `/fulcrum` dashboard)
- `GET /decisioning/summary` — bucket counts, sector heat, alignment
- `GET /decisioning/companies` — paginated with `q`, `sector`, `bucket`, `cohort`, `model_alignment` filters
- `GET /decisioning/companies/{cin}` — single company detail
- `GET /decisioning/report` — renders [docs/DECISIONING_SUMMARY_REPORT.md](docs/DECISIONING_SUMMARY_REPORT.md)

### Legacy / model registry
- `POST /score-company-csv`, `POST /score-company-json` — score a raw feature vector
- `GET /models`, `GET /models/{model_name}` — full catalog; detailed field reference in [notes/models.md](notes/models.md)
- `GET /health` — bundle + rule-set version sanity check

### Response contracts
Pydantic schemas in [api/report_contract.py](api/report_contract.py) — `ReportJobStatus`, `ReportSectionKind` (15 section kinds including `executive_judgment`, `balance_sheet_risk`, `liquidity_cash_flow`, `governance_audit`, `key_red_flags`, `trend_view`, etc.), `SectionProvenance` (`deterministic | model_derived | llm_synthesized | source_grounded`), `Severity` (`info | watch | warning | critical`).

---

## 6. Storage model

**No database.** Everything is file-backed under [data/](data/) and [artifacts/](artifacts/):

```
data/
  cibil/                               # raw cohort seeds
  processed/
    data.csv                           # raw extracted 300-row table
    model_features.csv                 # engineered (121 cols)
    training_matrix_tier1a.csv         # active training set
    decisioning_output_latest.csv      # powers /fulcrum dashboard
    decisioning_output_years.csv       # per-year detail
    scored_companies.csv               # cohort-wide engine scores
  report_jobs/{job_id}/                # live job state (per upload)
    job.json                           # status + progress
    events.jsonl                       # append-only SSE event log
    upload.pdf                         # uploaded document
    gemini_extraction.json             # raw LLM extraction
    extracted_model_input.csv          # normalized feature row
    result.json                        # final completed report

artifacts/
  models/
    {name}.joblib                      # trained model bundle
    {name}_threshold.json              # chosen probability cutoff
    {name}_features.json               # input + transformed columns
    production_model.json              # pin for the engine
  reports/
    model_leaderboard.csv
    validation_metrics.json / test_metrics.json
    grouped_cv_summary.csv / grouped_cv_fold_metrics.csv
    {model}_coefficients.csv / _feature_importance.csv
```

Jobs persist across server restarts. No cleanup job — the `data/report_jobs/` directory grows monotonically.

---

## 7. Frontend

- **Next.js 16**, **React 19**, **TypeScript**, **Tailwind v4** (minimal deps — see [frontend/package.json](frontend/package.json); no UI framework, just Tailwind).
- Proxies `/api/*` → `http://127.0.0.1:8000` (override with `NEXT_PUBLIC_FULCRUM_API_BASE`). Proxy wrappers: [frontend/app/api/_backend.ts](frontend/app/api/_backend.ts) and [frontend/app/api/decisioning/_decisioningProxy.ts](frontend/app/api/decisioning/_decisioningProxy.ts).
- Workspace pattern: each route has a `page.tsx` (server component) that delegates to a `-workspace.tsx` client component (e.g. [fulcrum-workspace.tsx](frontend/app/fulcrum/fulcrum-workspace.tsx), [report-run-workspace.tsx](frontend/app/fulcrum/report/[jobId]/report-run-workspace.tsx), [processing-workspace.tsx](frontend/app/fulcrum/report/[jobId]/processing/processing-workspace.tsx), [report-upload-workspace.tsx](frontend/app/fulcrum/report/new/report-upload-workspace.tsx)).
- Typed API boundary in [frontend/app/fulcrum/api.ts](frontend/app/fulcrum/api.ts) and [frontend/app/fulcrum/types.ts](frontend/app/fulcrum/types.ts).
- Print-friendly report CSS landed recently (see commit `43ec1bf`).

---

## 8. Extraction prompt design (LLM boundary)

The LLM is **deliberately restricted** to source-grounded extraction. See the header docstring of [scripts/gemini_report_extractor.py](scripts/gemini_report_extractor.py):

> "The LLM is used only to extract source-grounded facts from PDFs. Normalization, ratio calculation, model scoring, and decision logic stay deterministic in the report runner."

Required Tier-1A raw fields (14) — revenue, PAT, interest expense, tax, depreciation, EBITDA, total equity / borrowings / assets, retained earnings, CFO/CFI/CFF, net cash change. Optional context fields (12) — current assets/liabilities, cash, inventory, receivables, capex, auditor opinion type & name, contingent liabilities, promoter holding %, emphasis of matter, going concern, fraud reported.

Model: `gemini-2.5-flash`. Basis detection prompts the model to report `scale_detected` (crore / lakh / million / thousand / absolute INR) so unit reconciliation is deterministic downstream.

Memo synthesis is a second LLM call; if it fails, the runner falls back to deterministic template sections (see `SectionProvenance.deterministic`).

---

## 9. Documentation map

| Doc | What it's for |
|---|---|
| [Readme.md](Readme.md) | Canonical intro — routes, API surface, pipeline mapping |
| [work.md](work.md) | 57KB development log — running narrative of decisions |
| [notes/models.md](notes/models.md) | Field-by-field reference for `GET /models` response |
| [notes/report.md](notes/report.md) | Project snapshot as of 2026-03-05 (stale on prod-model pin — see §4.4) |
| [docs/ANNUAL_REPORT_API_CONTRACT.md](docs/ANNUAL_REPORT_API_CONTRACT.md) | Contract for report endpoints + event stream |
| [docs/CIBIL_MCA_PIPELINE.md](docs/CIBIL_MCA_PIPELINE.md) | How the defaulter cohort was sourced |
| [docs/DATA_SOURCES_WILFUL_DEFAULTERS.md](docs/DATA_SOURCES_WILFUL_DEFAULTERS.md) | Raw data provenance |
| [docs/DECISIONING_SUMMARY_REPORT.md](docs/DECISIONING_SUMMARY_REPORT.md) | Rendered at `/decisioning/report` |
| [docs/DEMO_COMPANY_INPUT_RULES.md](docs/DEMO_COMPANY_INPUT_RULES.md) | Valid input shape for demo CSVs |
| [docs/FINANCIAL_DOWNLOAD_AUTOMATION.md](docs/FINANCIAL_DOWNLOAD_AUTOMATION.md) | Moneycontrol scraping plan |
| [docs/MCA_ALTERNATIVES_AND_WORKAROUNDS.md](docs/MCA_ALTERNATIVES_AND_WORKAROUNDS.md) | When MCA data isn't accessible |
| [docs/TIER1_FEATURE_DICTIONARY.md](docs/TIER1_FEATURE_DICTIONARY.md) | **Ground-truth feature definitions** |

---

## 10. Known caveats & sharp edges

1. **Small cohort (100 companies × 3 FY = 300 rows).** Metrics look excellent (test PR-AUC ~0.92–0.96) but overfitting and shortcut learning are real risks. `notes/report.md` §10 explicitly flags this.
2. **Class imbalance trickery.** 50/50 defaulter/control is artificial vs. real-world base rates — calibrated probabilities are trained on a balanced sample and may not be meaningful as absolute probabilities in production.
3. **`notes/report.md` is stale** — it states production model is `logistic_regression` with threshold 0.78 (old). The live pin in `production_model.json` is `hist_gradient_boosting`. Trust the manifest, not the notes.
4. **Some features in `feature_spec.yaml` are not yet extracted** (auditor flags, shareholding history, Beneish M). The Tier-1A feature set in use is a deliberate minimum.
5. **No authentication.** CORS is open (`allow_origins=["*"]`) and there's no auth on any endpoint.
6. **No job cleanup.** `data/report_jobs/` grows forever.
7. **Gemini-only extraction.** Extraction is coupled to `gemini-2.5-flash`. An outage or rate-limit breaks the pipeline. Memo synthesis has a deterministic fallback; extraction does not.
8. **Sector taxonomy is hardcoded.** `KNOWN_SECTORS` + `KEYWORD_SECTORS` in [report_job_runner.py:26-69](scripts/report_job_runner.py#L26). New sectors fall back to keyword-matching heuristics.
9. **`risk_rules.yaml` references features the Tier-1A model does not include** (`interest_coverage`, `contingent_to_networth_ratio`, `auditor_qualification_flag`, trend features). These apply at the **decision layer** on extracted/derived fields, independent of the ML feature vector — expect rule-flag counts to reflect extraction coverage, not model input.

---

## 11. Running locally

```bash
# Backend
export GEMINI_API_KEY=...
python -m uvicorn api.predict:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
# → http://localhost:3000
```

See [.env.example](.env.example) for environment variables. Python deps in [requirements.txt](requirements.txt) are lean: FastAPI/uvicorn, pandas/numpy, scikit-learn/joblib, `google-genai`, `camelot-py[cv]` + `pdfplumber` + `playwright` (PDF-extraction fallbacks, largely unused in the current LLM-first flow), `pyyaml`.

---

## 12. Mental model to carry forward

- **The LLM is an extractor, not a scorer.** Keep ML deterministic; keep the "intelligence" in the prompt + the two-model cross-check.
- **The cohort dashboard (`/fulcrum`) is calibration furniture.** It exists so a reader of a single report knows what a "71" actually means relative to 100 labeled outcomes.
- **Everything is a file.** No DB, no queue, no cache. The SSE stream is the real-time layer; the JSONL event log is the durable one.
- **Two specs, one in use.** `feature_spec.yaml` is aspirational; `tier1a_v1` is live. When in doubt, trust the config a training run would actually load.
- **Print is a first-class surface.** The report page was recently given a print-friendly layout — credit committees print things.
