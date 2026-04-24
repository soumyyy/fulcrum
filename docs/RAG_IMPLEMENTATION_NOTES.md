# RAG Implementation Notes

This repository now contains a standalone, unwired RAG layer for annual-report evidence retrieval.

## Purpose

The RAG layer is intended for:

- retrieving relevant annual-report text chunks for report-section generation,
- grounding qualitative sections such as audit, contingent liabilities, and business profile,
- supporting later report-page Q&A.

It is intentionally **not** used for:

- field extraction,
- ratio calculation,
- model scoring,
- decision bucket logic.

## Current implementation

Script:
- `/Users/soumya/Desktop/Projects/fulcrum/scripts/report_rag.py`

Backend type:
- local TF-IDF retrieval over chunked annual-report text

Core capabilities:
- extract page-wise text from PDF using `pdfplumber`
- chunk pages into overlapping sentence windows
- classify chunks into coarse section types
- build and persist a local retrieval index
- run free-text retrieval queries
- retrieve evidence for predefined report sections
- build an LLM-ready context block for a section

## Why TF-IDF first

This version is intentionally lightweight and uses only libraries already present in the project.
That makes it real, demonstrable, and easy to inspect without changing the live product pipeline.

A future version can swap the retrieval backend for dense embeddings while keeping the same chunking and retrieval interface.

## Example commands

Build an index:

```bash
./.venv/bin/python scripts/report_rag.py build \
  --pdf /path/to/annual_report.pdf \
  --out-dir data/rag/demo_job
```

Run a free-text query:

```bash
./.venv/bin/python scripts/report_rag.py query \
  --index-dir data/rag/demo_job \
  --query "What does the auditor say about going concern?"
```

Retrieve evidence for the governance section:

```bash
./.venv/bin/python scripts/report_rag.py section \
  --index-dir data/rag/demo_job \
  --section-id governance_audit
```

Build an LLM context block only:

```bash
./.venv/bin/python scripts/report_rag.py section \
  --index-dir data/rag/demo_job \
  --section-id governance_audit \
  --context-only
```

## Intended future integration points

If later wired into the report pipeline, the natural insertion points are:

- after PDF parse / before LLM report synthesis,
- section-level evidence retrieval in `report_job_runner.py`,
- an optional `/reports/{job_id}/ask` API for grounded Q&A.
