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
import sys
from typing import Any
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
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


def extraction_json_path(job_id: str) -> Path:
    return job_dir(job_id) / "gemini_extraction.json"


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


def log_job(job_id: str, message: str) -> None:
    print(f"[fulcrum-report:{job_id}] {message}", flush=True)


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
    log_job(
        job_id,
        f"status={job['status']} progress={job['progress_pct']} stage={job['current_stage']} message={job.get('message')}",
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


def _source_ref(job_id: str, field: str, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": f"src_{field}",
        "document_id": "annual_report_pdf",
        "page": item.get("page"),
        "table_id": None,
        "snippet": item.get("snippet"),
        "bounding_box": None,
    }


def _field_confidence(item: dict[str, Any]) -> float:
    try:
        value = float(item.get("confidence", 0.0))
    except (TypeError, ValueError):
        value = 0.0
    return max(0.0, min(1.0, value))


def _field_text(fields: dict[str, dict[str, Any]], field: str) -> str | None:
    item = fields.get(field, {})
    value = item.get("normalized_value")
    if value is None:
        value = item.get("value")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _contract_extractions(job_id: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    from gemini_report_extractor import extracted_fields_by_name

    fields = extracted_fields_by_name(payload)
    out: list[dict[str, Any]] = []
    for field, item in fields.items():
        if not isinstance(item, dict):
            continue
        source_ref = _source_ref(job_id, field, item)
        out.append(
            {
                "field": field,
                "value": item.get("value"),
                "normalized_value": item.get("normalized_value"),
                "unit": item.get("unit"),
                "scale": item.get("scale"),
                "period": item.get("period"),
                "basis": item.get("basis") or "unknown",
                "confidence": _field_confidence(item),
                "source_refs": [source_ref] if item.get("snippet") or item.get("page") else [],
                "warnings": list(item.get("warnings") or []),
            }
        )
    return out


def _validation_issues(payload: dict[str, Any], job_id: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for note in payload.get("validation_notes", []) or []:
        if not isinstance(note, dict):
            continue
        issues.append(
            {
                "field": note.get("field"),
                "severity": note.get("severity") or "info",
                "message": note.get("message") or "Gemini returned an extraction note.",
                "source_refs": [],
            }
        )

    document = payload.get("document", {}) if isinstance(payload.get("document"), dict) else {}
    for warning in document.get("warnings", []) or []:
        issues.append(
            {
                "field": None,
                "severity": "watch",
                "message": str(warning),
                "source_refs": [],
            }
        )

    if not issues:
        issues.append(
            {
                "field": None,
                "severity": "info",
                "message": "Gemini extraction returned without additional validation notes.",
                "source_refs": [],
            }
        )
    return issues


def _build_raw_dataframe(job: dict[str, Any], extraction_payload: dict[str, Any]):
    import pandas as pd

    from gemini_report_extractor import extracted_fields_by_name, numeric_or_none

    fields = extracted_fields_by_name(extraction_payload)
    document = extraction_payload.get("document", {}) if isinstance(extraction_payload.get("document"), dict) else {}
    job_company = dict(job.get("company", {}))

    def num(field: str) -> float | None:
        item = fields.get(field, {})
        if not item:
            return None
        value = item.get("normalized_value")
        if value is None:
            value = item.get("value")
        return numeric_or_none(value)

    def doc_text(field: str) -> str | None:
        value = document.get(field)
        if value is None:
            value = _field_text(fields, field)
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    company_name = doc_text("company_name") or job_company.get("company_name") or "Uploaded Company"
    cin = doc_text("cin") or job_company.get("cin") or f"UNKNOWN_{job['job_id']}"
    sector = doc_text("sector") or job_company.get("sector") or "Unknown"

    financial_year = numeric_or_none(document.get("financial_year"))
    if financial_year is None:
        financial_year = num("financial_year")
    if financial_year is None:
        raise ValueError("Gemini could not extract financial_year; model scoring cannot proceed.")

    row = {
        "company_name": company_name,
        "cin": cin,
        "financial_year": int(financial_year),
        "cohort": "uploaded",
        "sector": sector,
        "revenue": num("revenue"),
        "pat": num("pat"),
        "interest_expense": num("interest_expense"),
        "tax_expense": num("tax_expense"),
        "depreciation": num("depreciation"),
        "ebitda": num("ebitda"),
        "total_equity": num("total_equity"),
        "total_borrowings": num("total_borrowings"),
        "total_assets": num("total_assets"),
        "retained_earnings": num("retained_earnings"),
        "cfo": num("cfo"),
        "cfi": num("cfi"),
        "cff": num("cff"),
        "net_cash_change": num("net_cash_change"),
        "current_assets": num("current_assets"),
        "current_liabilities": num("current_liabilities"),
        "cash_and_equivalents": num("cash_and_equivalents"),
        "inventory": num("inventory"),
        "receivables": num("receivables"),
        "capex": num("capex"),
        "contingent_liabilities_amount": num("contingent_liabilities_amount"),
        "promoter_holding_pct": num("promoter_holding_pct"),
        "emphasis_of_matter": num("emphasis_of_matter"),
        "going_concern_uncertainty": num("going_concern_uncertainty"),
        "fraud_reported": num("fraud_reported"),
        "related_party_transactions_amount": num("related_party_transactions_amount"),
        "rpt_count": num("rpt_count"),
        "pending_legal_cases_count": num("pending_legal_cases_count"),
        "opinion_type": _field_text(fields, "opinion_type") or "",
        "auditor_name": _field_text(fields, "auditor_name") or "",
    }
    return pd.DataFrame([row])


def _score_extracted_dataframe(raw_df):
    import joblib

    from build_decisioning_output import DEFAULT_AUDIT_MODEL, build_outputs
    from build_training_matrix import load_config
    from risk_decision import load_rules
    from scoring_utils import DEFAULT_PRODUCTION_ALIAS, load_production_bundle

    train_config = load_config(PROJECT_ROOT / "config" / "model_train_config_tier1a.yaml")
    rules_config = load_rules(PROJECT_ROOT / "config" / "risk_rules.yaml")
    engine_bundle, _engine_manifest = load_production_bundle(DEFAULT_PRODUCTION_ALIAS)
    audit_bundle = joblib.load(DEFAULT_AUDIT_MODEL)
    years_df, latest_df = build_outputs(raw_df, train_config, rules_config, engine_bundle, audit_bundle)
    return years_df.iloc[0].to_dict(), latest_df.iloc[0].to_dict()


def _feature_values(raw_df) -> list[dict[str, Any]]:
    from build_model_features import build_features

    feature_df = build_features(raw_df.copy())
    if feature_df.empty:
        return []
    row = feature_df.iloc[0]
    features = [
        ("debt_to_assets", "higher_is_riskier"),
        ("ebitda_margin", "lower_is_riskier"),
        ("pat_margin", "lower_is_riskier"),
        ("roa", "lower_is_riskier"),
        ("retained_earnings_to_assets", "lower_is_riskier"),
        ("cfo_to_assets", "lower_is_riskier"),
        ("cfo_to_ebitda", "lower_is_riskier"),
        ("net_cash_change_to_assets", "lower_is_riskier"),
        ("log_total_assets", "contextual"),
        ("log_revenue", "contextual"),
    ]
    out: list[dict[str, Any]] = []
    for feature, direction in features:
        value = row.get(feature)
        if value != value:
            value = None
        out.append(
            {
                "feature": feature,
                "value": None if value is None else float(value),
                "display_value": None if value is None else f"{float(value):.4f}",
                "direction": direction,
                "percentile": None,
                "prior_year_delta": None,
            }
        )
    return out


def _build_scored_result(job: dict[str, Any], extraction_payload: dict[str, Any]) -> dict[str, Any]:
    raw_df = _build_raw_dataframe(job, extraction_payload)
    year_score, latest_score = _score_extracted_dataframe(raw_df)
    job_id = str(job["job_id"])
    document = extraction_payload.get("document", {}) if isinstance(extraction_payload.get("document"), dict) else {}

    basis = str(document.get("basis") or "standalone")
    if basis not in {"standalone", "consolidated"}:
        basis = "auto"

    company = {
        "company_name": str(raw_df["company_name"].iloc[0]),
        "cin": str(raw_df["cin"].iloc[0]),
        "sector": str(raw_df["sector"].iloc[0]),
        "financial_year": int(raw_df["financial_year"].iloc[0]),
        "basis_preference": basis,
    }
    model_output = {
        "engine_model_name": str(latest_score["engine_model_name"]),
        "engine_model_version": str(latest_score.get("engine_model_version", "")),
        "engine_probability": float(latest_score["engine_probability"]),
        "engine_score_0_100": float(latest_score["engine_score_0_100"]),
        "engine_risk_band": str(latest_score["engine_risk_band"]),
        "audit_model_name": str(latest_score["audit_model_name"]),
        "audit_probability": float(latest_score["audit_probability"]),
        "audit_score_0_100": float(latest_score["audit_score_0_100"]),
        "model_alignment": str(latest_score["model_alignment"]),
        "decision_bucket": str(latest_score["decision_bucket"]),
        "top_drivers": [
            item.strip()
            for item in str(latest_score.get("top_reasons", "")).split("|")
            if item.strip()
        ],
    }
    benchmark_output = {
        "sector": company["sector"],
        "overall_risk_percentile": float(year_score.get("overall_risk_percentile", 100.0)),
        "sector_risk_percentile": float(year_score.get("sector_risk_percentile", 100.0)),
        "peer_context": "Percentiles are computed from the current upload job scope until portfolio benchmark attachment is added.",
        "benchmark_notes": [
            "Uploaded report was scored through the Tier 1A engine and logistic audit baseline.",
            "Sector may be 'Unknown' if the annual report did not disclose a clean business category.",
        ],
    }
    extractions = _contract_extractions(job_id, extraction_payload)
    validation_issues = _validation_issues(extraction_payload, job_id)
    features = _feature_values(raw_df)
    sections = [
        {
            "section_id": "risk_snapshot",
            "kind": "risk_snapshot",
            "title": "Risk Snapshot",
            "status": "complete",
            "provenance": ["model_derived", "deterministic"],
            "markdown": (
                f"{company['company_name']} scored {model_output['engine_score_0_100']:.2f}/100 "
                f"with decision bucket {model_output['decision_bucket']}. "
                f"Audit baseline score: {model_output['audit_score_0_100']:.2f}/100."
            ),
            "data": model_output,
            "source_refs": [],
            "warnings": [],
        },
        {
            "section_id": "financial_stress",
            "kind": "financial_stress",
            "title": "Financial Stress Indicators",
            "status": "complete",
            "provenance": ["deterministic"],
            "markdown": "Tier 1A ratios were computed from Gemini-extracted annual-report fields and scored through the existing Fulcrum model stack.",
            "data": {"features": features},
            "source_refs": [],
            "warnings": [],
        },
        {
            "section_id": "analyst_conclusion",
            "kind": "analyst_conclusion",
            "title": "Analyst Conclusion",
            "status": "complete",
            "provenance": ["model_derived", "source_grounded"],
            "markdown": str(latest_score.get("support_summary", "Review extracted fields and model output before decisioning.")),
            "data": {"rule_flags_triggered": latest_score.get("rule_flags_triggered")},
            "source_refs": [],
            "warnings": [],
        },
    ]
    decision = {
        "job_id": job_id,
        "company": company,
        "status": "completed",
        "model_output": model_output,
        "benchmark_output": benchmark_output,
        "final_statement": str(latest_score.get("support_summary", "")),
        "confidence_statement": "Confidence depends on Gemini extraction confidence and validation notes; review source snippets before relying on the score.",
        "warnings": [issue["message"] for issue in validation_issues if issue.get("severity") in {"watch", "warning", "critical"}],
    }
    return {
        "job_id": job_id,
        "status": "completed",
        "company": company,
        "extractions": extractions,
        "validation_issues": validation_issues,
        "features": features,
        "model_output": model_output,
        "benchmark_output": benchmark_output,
        "sections": sections,
        "decision": decision,
    }


def run_report_job(job_id: str) -> dict[str, Any]:
    try:
        job = update_job(job_id, status="parsing", progress_pct=15, current_stage="uploading_to_gemini", message="Sending annual report to Gemini Files API.")
        pdf_path = Path(job["upload_path"])
        update_job(job_id, status="extracting", progress_pct=35, current_stage="extracting_fields", message="Extracting financial fields from the annual report.")

        from gemini_report_extractor import extract_annual_report_with_gemini

        def gemini_progress(message: str) -> None:
            log_job(job_id, message)
            append_event(job_id, "job.progress", {"current_stage": "extracting_fields", "message": message})
            lowered = message.lower()
            if "uploading pdf" in lowered:
                update_job(job_id, status="extracting", progress_pct=38, current_stage="uploading_pdf_to_gemini", message=message)
            elif "file is still processing" in lowered or "waiting for file processing" in lowered:
                update_job(job_id, status="extracting", progress_pct=42, current_stage="waiting_for_gemini_file_processing", message=message)
            elif "requesting structured extraction" in lowered:
                update_job(job_id, status="extracting", progress_pct=48, current_stage="waiting_for_gemini_extraction_response", message=message)
            elif "returned extraction response" in lowered:
                update_job(job_id, status="extracting", progress_pct=52, current_stage="gemini_extraction_received", message=message)

        extraction_payload = extract_annual_report_with_gemini(pdf_path, progress_callback=gemini_progress)
        write_json(extraction_json_path(job_id), extraction_payload)
        log_job(job_id, f"wrote Gemini extraction artifact: {extraction_json_path(job_id)}")

        update_job(job_id, status="validating", progress_pct=55, current_stage="normalizing_and_validating", message="Normalizing units and validating extracted values.")
        raw_df = _build_raw_dataframe(job, extraction_payload)
        raw_df.to_csv(job_dir(job_id) / "extracted_model_input.csv", index=False)
        log_job(job_id, f"wrote extracted model input: {job_dir(job_id) / 'extracted_model_input.csv'}")

        update_job(job_id, status="featurizing", progress_pct=70, current_stage="calculating_ratios", message="Calculating Tier 1A ratios.")
        _feature_values(raw_df)

        update_job(job_id, status="scoring", progress_pct=82, current_stage="scoring_models", message="Running engine and audit models.")
        result = _build_scored_result(job, extraction_payload)

        update_job(job_id, status="generating", progress_pct=92, current_stage="assembling_report", message="Assembling model-derived report package.")
        write_json(result_json_path(job_id), result)
        log_job(job_id, f"wrote report result artifact: {result_json_path(job_id)}")
        for section in result["sections"]:
            append_event(job_id, "section.complete", {"section": section})
        append_event(job_id, "job.complete", {"result_url": f"/reports/{job_id}"})

        return update_job(
            job_id,
            status="completed",
            progress_pct=100,
            current_stage="completed",
            message="Annual report extraction and model scoring completed.",
            completed_at=utc_now(),
        )
    except Exception as exc:  # noqa: BLE001
        return update_job(
            job_id,
            status="failed",
            progress_pct=100,
            current_stage="failed",
            message="Report job failed.",
            error=str(exc),
            completed_at=utc_now(),
        )


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
