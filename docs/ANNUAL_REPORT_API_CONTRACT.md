# Annual Report Analysis API Contract

This contract defines the upload-to-report workflow for the expert annual-report risk tool.

The contract is intentionally split from the existing portfolio API. The existing API serves the trained portfolio decisioning outputs. This workflow accepts a new annual report, extracts facts, scores the company, and streams a generated expert page.

## Product Boundary

V1 should support:

- one annual-report PDF per job
- one company per job
- deterministic extraction/feature/model stages
- LLM-generated report sections grounded only in validated facts, model output, benchmark output, and source references
- section-level streaming for the frontend

V1 should not support:

- multi-PDF reconciliation
- web enrichment
- unsourced claims
- LLM arithmetic
- silent unit conversion without warnings

## Endpoint Summary

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/reports/upload` | Upload annual report and create analysis job |
| `GET` | `/reports/{job_id}/status` | Poll job status |
| `GET` | `/reports/{job_id}/events` | Stream job events and section deltas over SSE |
| `GET` | `/reports/{job_id}` | Fetch full job result |
| `GET` | `/reports/{job_id}/sections` | Fetch generated report sections |
| `GET` | `/reports/{job_id}/evidence` | Fetch extracted datapoints and source refs |
| `GET` | `/reports/{job_id}/features` | Fetch calculated features/ratios |
| `GET` | `/reports/{job_id}/decision` | Fetch final model and analyst decision |
| `DELETE` | `/reports/{job_id}` | Delete job artifacts |

## Status Lifecycle

```text
queued -> parsing -> extracting -> validating -> featurizing -> scoring -> generating -> completed
```

Failure state:

```text
failed
```

The frontend should treat all statuses except `completed` and `failed` as active.

## POST /reports/upload

Creates an analysis job.

Request:

`multipart/form-data`

| Field | Type | Required | Notes |
|---|---|---:|---|
| `file` | PDF file | yes | Annual report PDF |
| `company_name` | string | no | User hint |
| `cin` | string | no | User hint |
| `sector` | string | no | User hint |
| `financial_year` | integer | no | User hint |
| `basis_preference` | enum | no | `standalone`, `consolidated`, or `auto`; default `standalone` |

Response `202`:

```json
{
  "job_id": "rpt_20260407_abc123",
  "status": "queued",
  "created_at": "2026-04-07T10:30:00Z",
  "upload_filename": "annual_report.pdf",
  "status_url": "/reports/rpt_20260407_abc123/status",
  "events_url": "/reports/rpt_20260407_abc123/events",
  "result_url": "/reports/rpt_20260407_abc123"
}
```

## GET /reports/{job_id}/status

Returns current job status.

Response:

```json
{
  "job_id": "rpt_20260407_abc123",
  "status": "extracting",
  "progress_pct": 35,
  "current_stage": "extracting_financial_tables",
  "message": "Reading balance sheet and cash-flow tables",
  "created_at": "2026-04-07T10:30:00Z",
  "updated_at": "2026-04-07T10:31:20Z",
  "completed_at": null,
  "error": null,
  "warnings": []
}
```

## GET /reports/{job_id}/events

Streams server-sent events.

Headers:

```http
Content-Type: text/event-stream
Cache-Control: no-cache
```

Event types:

- `job.status`
- `extraction.field`
- `validation.issue`
- `feature.computed`
- `model.scored`
- `section.delta`
- `section.complete`
- `job.complete`
- `job.error`

Example:

```text
event: section.delta
data: {"job_id":"rpt_20260407_abc123","section_id":"financial_stress","delta":"Cash-flow stress increased because..."}
```

The frontend should append `section.delta` chunks by `section_id`.

## GET /reports/{job_id}

Returns the full canonical job object.

Response shape:

```json
{
  "job_id": "rpt_20260407_abc123",
  "status": "completed",
  "company": {
    "company_name": "Example Ltd",
    "cin": "L00000XX0000PLC000000",
    "sector": "Steel & Metals",
    "financial_year": 2025,
    "basis_preference": "standalone"
  },
  "extractions": [],
  "validation_issues": [],
  "features": [],
  "model_output": {},
  "benchmark_output": {},
  "sections": [],
  "decision": {}
}
```

## Extraction Object

Every extracted datapoint must carry confidence and source references.

```json
{
  "field": "total_borrowings",
  "value": 12500.4,
  "normalized_value": 125.004,
  "unit": "INR crore",
  "scale": "crore",
  "period": "FY2025",
  "basis": "standalone",
  "confidence": 0.92,
  "source_refs": [
    {
      "source_id": "src_001",
      "document_id": "annual_report_pdf",
      "page": 143,
      "table_id": "balance_sheet_standalone",
      "snippet": "Borrowings ... 12,500.4"
    }
  ],
  "warnings": []
}
```

Required extraction fields for V1:

- `revenue`
- `pat`
- `interest_expense`
- `depreciation`
- `tax_expense`
- `ebitda`
- `total_equity`
- `total_borrowings`
- `total_assets`
- `retained_earnings`
- `cfo`
- `cfi`
- `cff`
- `net_cash_change`
- `current_assets`
- `current_liabilities`
- `cash_and_equivalents`
- `inventory`
- `receivables`
- `capex`
- `opinion_type`
- `auditor_name`
- `emphasis_of_matter`
- `contingent_liabilities_amount`
- `promoter_holding_pct`

Tier 1A can score if only its required raw fields are available, but the report should show missingness warnings for unavailable Tier 2 fields.

## Validation Issue Object

```json
{
  "field": "capex",
  "severity": "warning",
  "message": "Capex sign was normalized from cash-flow outflow to absolute capex value.",
  "source_refs": []
}
```

Severity values:

- `info`
- `watch`
- `warning`
- `critical`

## Feature Object

```json
{
  "feature": "debt_to_assets",
  "value": 0.67,
  "display_value": "67.0%",
  "direction": "higher_is_riskier",
  "percentile": 82.4,
  "prior_year_delta": 0.08
}
```

Minimum V1 feature set:

- `debt_to_assets`
- `ebitda_margin`
- `pat_margin`
- `roa`
- `retained_earnings_to_assets`
- `cfo_to_assets`
- `cfo_to_ebitda`
- `net_cash_change_to_assets`
- `log_total_assets`
- `log_revenue`

## Model Output Object

```json
{
  "engine_model_name": "hist_gradient_boosting",
  "engine_model_version": "tier1a_v1",
  "engine_probability": 0.752,
  "engine_score_0_100": 75.2,
  "engine_risk_band": "High",
  "audit_model_name": "logistic_regression",
  "audit_probability": 0.739,
  "audit_score_0_100": 73.9,
  "model_alignment": "agree",
  "decision_bucket": "urgent_review",
  "top_drivers": [
    "high leverage",
    "negative profitability",
    "weak operating cash flow"
  ]
}
```

## Benchmark Output Object

```json
{
  "sector": "Steel & Metals",
  "overall_risk_percentile": 96.0,
  "sector_risk_percentile": 88.0,
  "peer_context": "Risk score is elevated versus current portfolio and sector peers.",
  "benchmark_notes": [
    "Debt-to-assets is above sector median.",
    "ROA is in the weaker sector quartile."
  ]
}
```

## Report Section Object

```json
{
  "section_id": "financial_stress",
  "kind": "financial_stress",
  "title": "Financial Stress",
  "status": "complete",
  "provenance": ["model_derived", "source_grounded", "llm_synthesized"],
  "markdown": "The company shows elevated financial stress...",
  "data": {
    "debt_to_assets": 0.67,
    "cfo_to_assets": -0.03
  },
  "source_refs": [],
  "warnings": []
}
```

Required sections:

1. `header`
2. `executive_judgment`
3. `risk_snapshot`
4. `financial_stress`
5. `governance_audit`
6. `trend_view`
7. `source_evidence`
8. `analyst_conclusion`

## Decision Object

```json
{
  "job_id": "rpt_20260407_abc123",
  "company": {
    "company_name": "Example Ltd",
    "cin": "L00000XX0000PLC000000",
    "sector": "Steel & Metals",
    "financial_year": 2025,
    "basis_preference": "standalone"
  },
  "status": "completed",
  "model_output": {},
  "benchmark_output": {},
  "final_statement": "Risk appears elevated and has worsened versus the prior available year...",
  "confidence_statement": "Medium confidence: core Tier 1A fields were extracted, but governance fields require manual review.",
  "warnings": []
}
```

## Frontend Rendering Contract

The frontend should render in this order:

1. job status/progress
2. streamed sections as they complete
3. evidence drawer keyed by `source_refs`
4. final decision card

Frontend should use:

- `decision_bucket` as workflow state
- `engine_score_0_100` for ranking
- `model_alignment` for confidence
- `validation_issues` and `warnings` for analyst caveats
- `source_refs` for traceability

The frontend should not display LLM text as final unless the section includes either:

- source refs, or
- explicit model/feature provenance.

## Error Contract

All API errors should return:

```json
{
  "detail": "Human-readable error message"
}
```

Common status codes:

- `400`: invalid request or unreadable PDF
- `404`: job id not found
- `409`: job not ready for requested result
- `413`: PDF too large
- `422`: extraction failed schema validation
- `500`: internal pipeline failure

## Implementation Notes

- Persist job state before starting extraction.
- Store uploaded PDFs under a job-specific directory.
- Store intermediate artifacts as JSON so failed jobs can be inspected.
- SSE should stream text deltas, but final persisted sections must be full section objects.
- Do arithmetic and model scoring outside the LLM.
- LLM synthesis must only see validated facts, model output, benchmark output, and source refs.
