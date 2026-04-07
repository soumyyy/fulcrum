#!/usr/bin/env python3
"""
File-backed annual-report analysis job runner.

This is the V0 skeleton: it persists jobs and emits schema-correct stub results so
the frontend can build against stable API behavior before extraction/LLM internals
are connected.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
from typing import Any
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORT_JOBS_DIR = PROJECT_ROOT / "data" / "report_jobs"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sanitize_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", filename.strip())
    return cleaned or "annual_report.pdf"


def make_job_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"rpt_{stamp}_{uuid4().hex[:10]}"


def job_dir(job_id: str) -> Path:
    return REPORT_JOBS_DIR / job_id


def job_json_path(job_id: str) -> Path:
    return job_dir(job_id) / "job.json"


def result_json_path(job_id: str) -> Path:
    return job_dir(job_id) / "result.json"


def events_path(job_id: str) -> Path:
    return job_dir(job_id) / "events.jsonl"


def upload_path(job_id: str, filename: str = "upload.pdf") -> Path:
    return job_dir(job_id) / filename


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"JSON artifact not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact is not an object: {path}")
    return payload


def append_event(job_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    event = {
        "event_id": uuid4().hex,
        "event": event_type,
        "created_at": utc_now(),
        "job_id": job_id,
        "data": payload,
    }
    path = events_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")
    return event


def read_events(job_id: str) -> list[dict[str, Any]]:
    path = events_path(job_id)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return events


def update_job(job_id: str, **updates: Any) -> dict[str, Any]:
    job = read_job(job_id)
    job.update(updates)
    job["updated_at"] = utc_now()
    write_json(job_json_path(job_id), job)
    append_event(
        job_id,
        "job.status",
        {
            "status": job["status"],
            "progress_pct": job["progress_pct"],
            "current_stage": job["current_stage"],
            "message": job.get("message"),
        },
    )
    return job


def read_job(job_id: str) -> dict[str, Any]:
    return read_json(job_json_path(job_id))


def read_result(job_id: str) -> dict[str, Any]:
    return read_json(result_json_path(job_id))


def create_job(
    *,
    upload_filename: str,
    company_name: str | None = None,
    cin: str | None = None,
    sector: str | None = None,
    financial_year: int | None = None,
    basis_preference: str = "standalone",
) -> tuple[dict[str, Any], Path]:
    job_id = make_job_id()
    created_at = utc_now()
    safe_filename = sanitize_filename(upload_filename)
    if not safe_filename.lower().endswith(".pdf"):
        safe_filename = f"{safe_filename}.pdf"
    destination = upload_path(job_id, safe_filename)
    destination.parent.mkdir(parents=True, exist_ok=False)

    job = {
        "job_id": job_id,
        "status": "queued",
        "progress_pct": 0,
        "current_stage": "queued",
        "message": "Annual report upload accepted.",
        "created_at": created_at,
        "updated_at": created_at,
        "completed_at": None,
        "error": None,
        "warnings": [],
        "upload_filename": upload_filename,
        "stored_filename": safe_filename,
        "upload_path": str(destination),
        "company": {
            "company_name": company_name,
            "cin": cin,
            "sector": sector,
            "financial_year": financial_year,
            "basis_preference": basis_preference,
        },
    }
    write_json(job_json_path(job_id), job)
    events_path(job_id).write_text("", encoding="utf-8")
    append_event(job_id, "job.status", {"status": "queued", "progress_pct": 0, "current_stage": "queued"})
    return job, destination


def save_upload_bytes(destination: Path, content: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)


def delete_job(job_id: str) -> None:
    path = job_dir(job_id)
    if not path.exists():
        raise FileNotFoundError(f"Job not found: {job_id}")
    shutil.rmtree(path)


def _company_hint(job: dict[str, Any]) -> dict[str, Any]:
    company = dict(job.get("company", {}))
    return {
        "company_name": company.get("company_name") or "Uploaded Company",
        "cin": company.get("cin"),
        "sector": company.get("sector") or "Unknown",
        "financial_year": company.get("financial_year"),
        "basis_preference": company.get("basis_preference") or "standalone",
    }


def _build_stub_result(job: dict[str, Any]) -> dict[str, Any]:
    job_id = str(job["job_id"])
    company = _company_hint(job)
    source_ref = {
        "source_id": "src_upload_stub",
        "document_id": "annual_report_pdf",
        "page": None,
        "table_id": None,
        "snippet": "V0 skeleton has not performed real PDF extraction yet.",
        "bounding_box": None,
    }
    model_output = {
        "engine_model_name": "hist_gradient_boosting",
        "engine_model_version": "tier1a_v1",
        "engine_probability": 0.0,
        "engine_score_0_100": 0.0,
        "engine_risk_band": "Pending real extraction",
        "audit_model_name": "logistic_regression",
        "audit_probability": 0.0,
        "audit_score_0_100": 0.0,
        "model_alignment": "agree",
        "decision_bucket": "manual_check",
        "top_drivers": ["PDF extraction pipeline not connected yet"],
    }
    benchmark_output = {
        "sector": company.get("sector"),
        "overall_risk_percentile": None,
        "sector_risk_percentile": None,
        "peer_context": "Benchmarking will run after validated Tier 1A fields are extracted.",
        "benchmark_notes": ["V0 skeleton output; no real model score has been computed."],
    }
    sections = [
        {
            "section_id": "header",
            "kind": "header",
            "title": "Uploaded Annual Report",
            "status": "complete",
            "provenance": ["deterministic"],
            "markdown": f"Uploaded report accepted for **{company['company_name']}**. This is a skeleton result until PDF extraction is connected.",
            "data": {"upload_filename": job.get("upload_filename")},
            "source_refs": [source_ref],
            "warnings": ["Stub section: no real extraction performed yet."],
        },
        {
            "section_id": "risk_snapshot",
            "kind": "risk_snapshot",
            "title": "Risk Snapshot",
            "status": "complete",
            "provenance": ["model_derived"],
            "markdown": "Model scoring is waiting for validated financial fields. The frontend can render this section now and replace it with live content later.",
            "data": model_output,
            "source_refs": [],
            "warnings": ["Model score is a placeholder."],
        },
        {
            "section_id": "analyst_conclusion",
            "kind": "analyst_conclusion",
            "title": "Analyst Conclusion",
            "status": "complete",
            "provenance": ["llm_synthesized"],
            "markdown": "No investment or credit conclusion should be drawn from this stub. The next backend step is to connect PDF extraction, validation, Tier 1A feature computation, and grounded LLM synthesis.",
            "data": {},
            "source_refs": [],
            "warnings": ["Placeholder analyst conclusion."],
        },
    ]
    decision = {
        "job_id": job_id,
        "company": company,
        "status": "completed",
        "model_output": model_output,
        "benchmark_output": benchmark_output,
        "final_statement": "Skeleton job completed. Real default-risk assessment requires extraction and validation.",
        "confidence_statement": "No analytical confidence yet; this is a transport and persistence skeleton.",
        "warnings": ["V0 stub result only."],
    }
    return {
        "job_id": job_id,
        "status": "completed",
        "company": company,
        "extractions": [
            {
                "field": "annual_report_pdf",
                "value": job.get("upload_filename"),
                "normalized_value": job.get("stored_filename"),
                "unit": None,
                "scale": None,
                "period": None,
                "basis": "unknown",
                "confidence": 1.0,
                "source_refs": [source_ref],
                "warnings": ["File persisted; data extraction pending."],
            }
        ],
        "validation_issues": [
            {
                "field": None,
                "severity": "watch",
                "message": "This job used the V0 skeleton runner; no PDF facts were extracted.",
                "source_refs": [source_ref],
            }
        ],
        "features": [],
        "model_output": model_output,
        "benchmark_output": benchmark_output,
        "sections": sections,
        "decision": decision,
    }


def run_stub_report_job(job_id: str) -> dict[str, Any]:
    try:
        job = update_job(job_id, status="parsing", progress_pct=15, current_stage="parsing_pdf", message="Parsing uploaded PDF.")
        update_job(job_id, status="extracting", progress_pct=35, current_stage="extracting_fields", message="Preparing extraction schema.")
        update_job(job_id, status="validating", progress_pct=55, current_stage="validating_fields", message="Preparing validation checks.")
        update_job(job_id, status="featurizing", progress_pct=70, current_stage="computing_features", message="Preparing Tier 1A feature computation.")
        update_job(job_id, status="scoring", progress_pct=82, current_stage="model_scoring", message="Preparing model scoring.")
        update_job(job_id, status="generating", progress_pct=92, current_stage="generating_sections", message="Generating stub report sections.")

        result = _build_stub_result(job)
        write_json(result_json_path(job_id), result)
        for section in result["sections"]:
            append_event(job_id, "section.complete", {"section": section})
        append_event(job_id, "job.complete", {"result_url": f"/reports/{job_id}"})

        return update_job(
            job_id,
            status="completed",
            progress_pct=100,
            current_stage="completed",
            message="Stub report job completed.",
            completed_at=utc_now(),
        )
    except Exception as exc:  # noqa: BLE001
        update_job(
            job_id,
            status="failed",
            progress_pct=100,
            current_stage="failed",
            message="Report job failed.",
            error=str(exc),
            completed_at=utc_now(),
        )
        raise
