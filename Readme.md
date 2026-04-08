# Fulcrum

AI-powered annual report risk analysis system for the Indian credit market. Upload any company's annual report PDF — Fulcrum extracts financial data, computes ratios, runs ML risk models, and writes a grounded analyst memo, end to end.

---

## What It Does

1. **Ingest** — upload an annual report PDF via the web UI
2. **Extract** — Gemini parses the document and pulls ~25 financial fields (revenue, PAT, EBITDA, borrowings, CFO, contingent liabilities, etc.)
3. **Validate & Normalize** — extracted values are unit-reconciled and normalized to INR crore; inconsistencies are flagged
4. **Featurize** — computes 10 Tier-1A financial ratios (debt/assets, EBITDA margin, ROA, CFO/EBITDA, etc.)
5. **Score** — two ML models run in parallel: a primary engine and a benchmark audit model; outputs a 0–100 risk score and a decision bucket
6. **Synthesize** — an LLM writes a structured analyst memo grounded in the extracted data (with fallback to deterministic sections if the LLM is unavailable)
7. **Report** — the full result is streamed to a report page in real time as each stage completes

---

## System Architecture

```
frontend/          Next.js 15 app (React 19, TypeScript, Tailwind)
api/               FastAPI backend (Python)
scripts/           ML pipeline, report job runner, feature engineering
config/            Feature spec, model config
data/              Training data, historical cohort, report job storage
artifacts/         Trained model artifacts (.joblib), thresholds, reports
```

### Request Flow

```
Browser → POST /api/reports/upload (Next.js proxy)
        → POST /reports/upload (FastAPI)
        → creates job in /data/report_jobs/{job_id}/
        → schedules background task: run_report_job()

Browser → GET /api/reports/{jobId}/events (Server-Sent Events)
        → streams live progress + section events to the processing page

Background task:
  1. Upload PDF to Gemini Files API
  2. Extract fields with Gemini flash
  3. Validate + normalize monetary units
  4. Calculate financial ratios
  5. Score with engine + audit ML models
  6. LLM synthesis → emit section.complete events
  7. Write result.json → emit job.complete
```

---

## Frontend Routes

| Route | Purpose |
|-------|---------|
| `/` | Landing page |
| `/fulcrum` | Model diagnostics dashboard — score distributions, bucket breakdown, sector heat, model agreement across the historical universe |
| `/fulcrum/report/new` | Upload page — drag-and-drop PDF upload with a slide-in sidebar for previous analyses |
| `/fulcrum/report/[jobId]/processing` | 10-step processing view — real-time step-by-step progress (Claude-style thinking UI), auto-redirects to report on completion |
| `/fulcrum/report/[jobId]` | Full report page — company overview, analyst memo, ratio appendix, model decision, financial snapshot, validation panel; all streamed in real time |
| `/models` | Model registry — lists trained artifacts with metadata |
| `/score` | Batch CSV scoring (legacy, for direct feature-vector inputs) |

---

## Backend API

All routes are served by FastAPI at `http://127.0.0.1:8000`. The Next.js app proxies them under `/api/*`.

### Report Pipeline

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/reports/upload` | Accept PDF, create job, schedule background analysis |
| `GET` | `/reports` | List all jobs (paginated, includes summaries) |
| `GET` | `/reports/{job_id}/status` | Current job status + progress percentage |
| `GET` | `/reports/{job_id}/events` | Server-Sent Events stream (status, progress, sections, complete) |
| `GET` | `/reports/{job_id}` | Full completed result (available after job.complete) |

### Decisioning (Historical Universe)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/decisioning/summary` | Portfolio-level stats: bucket counts, alignment, sector summary |
| `GET` | `/decisioning/companies` | Paginated company list with scores and buckets |
| `GET` | `/decisioning/companies/{cin}` | Single company detail |

### Legacy Scoring

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/score-company-csv` | Score a company from a feature-vector CSV row |
| `POST` | `/score-company-json` | Score a company from a JSON feature vector |
| `GET` | `/models` | List registered model artifacts |

---

## Processing Pipeline Details

The background job runner (`scripts/report_job_runner.py`) emits status and progress updates over Server-Sent Events. The 10-step processing page maps to these backend stages:

| Step | Backend stage | Approx. progress |
|------|--------------|-----------------|
| Document received | queued | 0% |
| Parsing document structure | parsing | 15% |
| Sending to extraction engine | uploading_pdf_to_gemini | 38% |
| Extracting financial data | waiting_for_gemini_extraction_response | 48% |
| Validating extracted fields | normalizing_and_validating | 55% |
| Normalizing monetary units | — (sub-step) | 62% |
| Computing financial ratios | calculating_ratios | 70% |
| Running risk models | scoring_models | 82% |
| Generating analyst memo | generating_analyst_report | 92% |
| Assembling report package | — (sub-step) | 96% |

---

## Report Output

A completed report contains:

- **Company profile** — name, CIN, financial year, sector, basis (standalone/consolidated)
- **Extracted fields** — ~25 monetary and non-monetary fields with normalized values, confidence scores, and source references
- **Validation issues** — unit mismatches, missing fields, inconsistency warnings
- **Financial ratios** — 10 primary model features + 5 supplementary ratios with analyst benchmarks and interpretation notes
- **Model output** — engine score (0–100), audit score, decision bucket, model alignment, top risk drivers
- **Analyst memo** — 6–10 LLM-synthesized sections: executive judgment, balance sheet risk, profitability, cash flow quality, contingent exposures, final decision
- **Decision** — final statement combining model output and analytical judgment with confidence framing

---

## ML Models

Two models run in parallel for every report:

| Model | Role |
|-------|------|
| **Engine** (primary) | Trained on the full historical defaulter cohort; outputs primary risk score and decision bucket |
| **Audit** (benchmark) | Independent model for cross-validation; disagreement between the two triggers `manual_check` |

Both models were trained on a cohort of 100 companies (50 wilful defaulters + 50 control) across 3 financial years (300 rows). Features are Tier-1A financial ratios derived from balance sheet, P&L, and cash flow statements.

### Decision Buckets

| Bucket | Meaning |
|--------|---------|
| `urgent_review` | Both models signal high risk — escalate immediately |
| `review` | Primary engine flags high risk — senior analyst sign-off required |
| `manual_check` | Models disagree or signal is mixed — human review needed |
| `watchlist` | Low risk but flags present — periodic monitoring |
| `monitor` | Clean signal — standard cadence |

---

## Historical Universe (`/fulcrum` dashboard)

The `/fulcrum` page is a calibration tool, not a live scoring surface. It shows:

- **Score distribution** — how the 0–100 scores spread across the 100-company historical cohort
- **Bucket breakdown** — how many companies landed in each action bucket
- **Cohort separation** — average score per labeled cohort (defaulters should score materially higher than controls)
- **Top drivers** — most frequently surfaced risk reasons across the cohort
- **Sector heat** — average score and urgent-review rate by sector

Use it to calibrate what a score of 70 or a `review` bucket actually means before interpreting a new report.

---

## Running Locally

### Backend

```bash
cd /path/to/fulcrum
python -m uvicorn api.predict:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

The frontend proxies all `/api/*` requests to `http://127.0.0.1:8000`. To change the backend URL, set `NEXT_PUBLIC_FULCRUM_API_BASE` in `frontend/.env.local`.

### Environment

The report pipeline requires a Gemini API key for PDF extraction and LLM synthesis. Set it in your environment before starting the backend:

```bash
export GEMINI_API_KEY=your_key_here
```

---

## Data Storage

Report jobs are stored as flat files under `data/report_jobs/{job_id}/`:

```
data/report_jobs/{job_id}/
  ├── job.json                   # Live status, progress, stage
  ├── events.jsonl               # Full event log (append-only)
  ├── upload.pdf                 # Uploaded document
  ├── gemini_extraction.json     # Raw Gemini extraction response
  ├── extracted_model_input.csv  # Normalized feature row
  └── result.json                # Final completed report
```

No database required. Jobs persist across server restarts.

---

## Project Context

Fulcrum was built to address a gap in Indian credit risk: most banks rely on manual annual report review and simple ratio checks. The system automates the extraction and ratio pipeline, then layers ML scoring trained on actual wilful defaulter outcomes — companies where the result is known.

The analyst memo is not a replacement for human judgment. It is a first-pass read that surfaces the signals worth investigating, so an analyst can spend time on judgment rather than data extraction.
