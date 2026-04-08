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
KNOWN_SECTORS = {
    "Cement",
    "Engineering / Manufacturing",
    "FMCG / Foods",
    "FMCG / Foods / Agro",
    "Gems & Jewellery",
    "IT / Services",
    "Infrastructure",
    "Logistics",
    "Media",
    "Mining",
    "NBFC / Leasing",
    "Oil & Gas",
    "Oil & Gas / Energy",
    "Pharma",
    "Real Estate",
    "Shipbuilding",
    "Steel & Metals",
    "Textiles",
    "Travel / Aviation",
    "Travel / Aviation / Hospitality",
    "Travel / Hospitality",
}
KEYWORD_SECTORS = [
    (("cement",), "Cement"),
    (("pharma", "laboratories", "drug", "healthcare"), "Pharma"),
    (("steel", "metal", "aluminium", "aluminum"), "Steel & Metals"),
    (("jewel", "diamond", "gems"), "Gems & Jewellery"),
    (("hotel", "hospitality", "resort"), "Travel / Hospitality"),
    (("aviation", "airline", "airways", "flight"), "Travel / Aviation"),
    (("travel", "tour", "holiday"), "Travel / Aviation / Hospitality"),
    (("finance", "leasing", "credit", "capital", "nbfc"), "NBFC / Leasing"),
    (("infra", "construction", "project", "engineering procurement"), "Infrastructure"),
    (("oil", "gas", "petroleum", "energy"), "Oil & Gas / Energy"),
    (("mining", "coal", "minerals"), "Mining"),
    (("logistics", "transport", "express", "shipping"), "Logistics"),
    (("shipyard", "shipbuilding"), "Shipbuilding"),
    (("textile", "fabric", "garment"), "Textiles"),
    (("media", "publication", "broadcast"), "Media"),
    (("food", "fmcg", "sugar", "agro", "consumer"), "FMCG / Foods / Agro"),
    (("software", "technology", "services", "it "), "IT / Services"),
    (("manufacturing", "equipment", "industrial", "electrical"), "Engineering / Manufacturing"),
    (("real estate", "developer", "properties"), "Real Estate"),
]


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


def _keyword_sector(company_name: str | None, gemini_sector: str | None) -> str | None:
    haystack = f"{company_name or ''} {gemini_sector or ''}".lower()
    for keywords, sector in KEYWORD_SECTORS:
        if any(keyword in haystack for keyword in keywords):
            return sector
    return None


def _resolve_sector(company_name: str | None, cin: str | None, gemini_sector: str | None) -> tuple[str, str, float]:
    cleaned_gemini_sector = (gemini_sector or "").strip()
    if cleaned_gemini_sector and cleaned_gemini_sector.lower() != "unknown":
        if cleaned_gemini_sector in KNOWN_SECTORS:
            return cleaned_gemini_sector, "gemini_taxonomy", 0.78
        keyword = _keyword_sector(company_name, cleaned_gemini_sector)
        if keyword:
            return keyword, "keyword_from_gemini_sector", 0.70
        return cleaned_gemini_sector, "gemini_free_text", 0.60

    keyword = _keyword_sector(company_name, None)
    if keyword:
        return keyword, "keyword_from_company_name", 0.58

    return "Unknown", "unresolved", 0.0


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


MONETARY_FIELDS = {
    "revenue",
    "pat",
    "interest_expense",
    "tax_expense",
    "depreciation",
    "ebitda",
    "total_equity",
    "total_borrowings",
    "total_assets",
    "retained_earnings",
    "cfo",
    "cfi",
    "cff",
    "net_cash_change",
    "current_assets",
    "current_liabilities",
    "cash_and_equivalents",
    "inventory",
    "receivables",
    "capex",
    "contingent_liabilities_amount",
    "related_party_transactions_amount",
}


def _reporting_context(payload: dict[str, Any], extractions: list[dict[str, Any]]) -> dict[str, Any]:
    document = payload.get("document", {}) if isinstance(payload.get("document"), dict) else {}
    monetary_scales: dict[str, int] = {}
    monetary_units: dict[str, int] = {}
    for item in extractions:
        if item.get("field") not in MONETARY_FIELDS:
            continue
        scale = str(item.get("scale") or "").strip()
        unit = str(item.get("unit") or "").strip()
        if scale:
            monetary_scales[scale] = monetary_scales.get(scale, 0) + 1
        if unit:
            monetary_units[unit] = monetary_units.get(unit, 0) + 1

    detected_scale = str(document.get("scale_detected") or "").strip()
    if not detected_scale and monetary_scales:
        detected_scale = max(monetary_scales, key=monetary_scales.get)

    detected_unit = str(document.get("currency") or "").strip()
    if monetary_units:
        detected_unit = max(monetary_units, key=monetary_units.get)
    if detected_unit and detected_scale and detected_unit.lower() == detected_scale.lower():
        source_basis = detected_scale
    else:
        source_basis = " ".join(part for part in [detected_unit, detected_scale] if part).strip()

    unit_confidence = "high" if detected_scale else "low"
    return {
        "source_currency": document.get("currency") or "INR",
        "source_scale_detected": detected_scale or None,
        "source_unit_basis": source_basis or None,
        "normalized_monetary_unit": "INR crore",
        "unit_confidence": unit_confidence,
        "note": (
            "Monetary values are shown after normalization to INR crore for model scoring. "
            "The original annual-report unit basis is retained in extracted field metadata."
        ),
    }


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
    if not document.get("scale_detected"):
        issues.append(
            {
                "field": "scale_detected",
                "severity": "watch",
                "message": "Annual-report monetary unit basis was not explicitly detected; monetary values are still normalized to INR crore for model scoring and should be source-checked.",
                "source_refs": [],
            }
        )

    for warning in document.get("warnings", []) or []:
        issues.append(
            {
                "field": None,
                "severity": "watch",
                "message": str(warning),
                "source_refs": [],
            }
        )

    sector_source = document.get("_fulcrum_sector_source")
    if sector_source == "unresolved":
        issues.append(
            {
                "field": "sector",
                "severity": "watch",
                "message": "Sector could not be resolved confidently from the annual report.",
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
    gemini_sector = doc_text("sector") or job_company.get("sector")
    sector, sector_source, sector_confidence = _resolve_sector(company_name, cin, gemini_sector)
    document["sector"] = sector
    document["_fulcrum_sector_source"] = sector_source
    document["_fulcrum_sector_confidence"] = sector_confidence
    document["_fulcrum_gemini_sector"] = gemini_sector

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


def _extraction_numeric(extractions: list[dict[str, Any]], field: str) -> float | None:
    from gemini_report_extractor import numeric_or_none

    for item in extractions:
        if item.get("field") != field:
            continue
        value = item.get("normalized_value")
        if value is None:
            value = item.get("value")
        return numeric_or_none(value)
    return None


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in {None, 0}:
        return None
    return float(numerator) / float(denominator)


def _supplementary_ratios_from_extractions(extractions: list[dict[str, Any]]) -> dict[str, float | None]:
    current_assets = _extraction_numeric(extractions, "current_assets")
    current_liabilities = _extraction_numeric(extractions, "current_liabilities")
    cash = _extraction_numeric(extractions, "cash_and_equivalents")
    total_assets = _extraction_numeric(extractions, "total_assets")
    contingent = _extraction_numeric(extractions, "contingent_liabilities_amount")
    ebitda = _extraction_numeric(extractions, "ebitda")
    interest = _extraction_numeric(extractions, "interest_expense")

    working_capital = None
    if current_assets is not None and current_liabilities is not None:
        working_capital = current_assets - current_liabilities

    return {
        "current_ratio": _safe_ratio(current_assets, current_liabilities),
        "cash_ratio": _safe_ratio(cash, current_liabilities),
        "working_capital_to_assets": _safe_ratio(working_capital, total_assets),
        "contingent_liabilities_to_assets": _safe_ratio(contingent, total_assets),
        "ebitda_to_interest": _safe_ratio(ebitda, interest),
    }


def _field_source_refs(extractions: list[dict[str, Any]], fields: set[str]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None, str | None]] = set()
    for item in extractions:
        if item.get("field") not in fields:
            continue
        for ref in item.get("source_refs", []) or []:
            key = (str(item.get("field")), ref.get("page"), ref.get("snippet"))
            if key in seen:
                continue
            seen.add(key)
            refs.append(ref)
    return refs


def _field_snapshot(extractions: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in extractions:
        field = item.get("field")
        value = item.get("normalized_value") if item.get("normalized_value") is not None else item.get("value")
        if field:
            out[str(field)] = value
    return out


def _risk_observations(features: list[dict[str, Any]], supplementary: dict[str, float | None], model_output: dict[str, Any]) -> list[str]:
    by_name = {str(item.get("feature")): item.get("value") for item in features}
    observations: list[str] = []

    debt_to_assets = by_name.get("debt_to_assets")
    if isinstance(debt_to_assets, (int, float)):
        if debt_to_assets > 0.5:
            observations.append(f"Debt/assets is elevated at {debt_to_assets:.2f}; leverage should be reviewed against sector peers.")
        else:
            observations.append(f"Debt/assets is {debt_to_assets:.2f}, below the internal 0.50 caution line.")

    cfo_to_ebitda = by_name.get("cfo_to_ebitda")
    if isinstance(cfo_to_ebitda, (int, float)):
        if cfo_to_ebitda < 0.5:
            observations.append(f"CFO/EBITDA is weak at {cfo_to_ebitda:.2f}; cash conversion is materially below the near-1.0 internal convention.")
        else:
            observations.append(f"CFO/EBITDA is {cfo_to_ebitda:.2f}; assess whether working capital explains the cash conversion level.")

    current_ratio = supplementary.get("current_ratio")
    if isinstance(current_ratio, (int, float)):
        if current_ratio < 1.0:
            observations.append(f"Current ratio is below 1.0 at {current_ratio:.2f}; near-term liquidity coverage is weak.")
        elif current_ratio < 1.5:
            observations.append(f"Current ratio is {current_ratio:.2f}; liquidity is positive but below the common 1.5-3.0 healthy range.")
        else:
            observations.append(f"Current ratio is {current_ratio:.2f}, within or above the common healthy range.")

    ebitda_to_interest = supplementary.get("ebitda_to_interest")
    if isinstance(ebitda_to_interest, (int, float)):
        if ebitda_to_interest < 1.5:
            observations.append(f"EBITDA/interest is weak at {ebitda_to_interest:.2f}.")
        elif ebitda_to_interest < 2.0:
            observations.append(f"EBITDA/interest is {ebitda_to_interest:.2f}, below the more comfortable 2.0x line.")
        else:
            observations.append(f"EBITDA/interest is {ebitda_to_interest:.2f}, above the 2.0x comfort line.")

    observations.append(
        f"Model bucket is {model_output.get('decision_bucket')} with primary risk score {float(model_output.get('engine_score_0_100', 0.0)):.2f}/100 and benchmark score {float(model_output.get('audit_score_0_100', 0.0)):.2f}/100."
    )
    return observations


def _public_model_context(model_output: dict[str, Any]) -> dict[str, Any]:
    return {
        "primary_risk_probability": model_output.get("engine_probability"),
        "primary_risk_score_0_100": model_output.get("engine_score_0_100"),
        "primary_risk_band": model_output.get("engine_risk_band"),
        "benchmark_probability": model_output.get("audit_probability"),
        "benchmark_score_0_100": model_output.get("audit_score_0_100"),
        "model_alignment": model_output.get("model_alignment"),
        "decision_bucket": model_output.get("decision_bucket"),
        "top_drivers": model_output.get("top_drivers", []),
    }


def _compact_extractions(extractions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = {
        "revenue",
        "pat",
        "ebitda",
        "total_assets",
        "total_borrowings",
        "total_equity",
        "retained_earnings",
        "cfo",
        "net_cash_change",
        "current_assets",
        "current_liabilities",
        "cash_and_equivalents",
        "contingent_liabilities_amount",
        "opinion_type",
        "auditor_name",
        "promoter_holding_pct",
        "emphasis_of_matter",
        "going_concern_uncertainty",
        "fraud_reported",
    }
    compact: list[dict[str, Any]] = []
    for item in extractions:
        if item.get("field") not in fields:
            continue
        compact.append(
            {
                "field": item.get("field"),
                "source_value": item.get("value"),
                "normalized_value": item.get("normalized_value"),
                "normalized_unit": "INR crore" if item.get("field") in MONETARY_FIELDS else item.get("unit"),
                "source_unit": item.get("unit"),
                "source_scale": item.get("scale"),
                "reporting_basis": item.get("basis"),
                "confidence": item.get("confidence"),
                "source": (item.get("source_refs") or [{}])[0].get("snippet") if item.get("source_refs") else None,
            }
        )
    return compact


def _fallback_sections(company: dict[str, Any], model_output: dict[str, Any], features: list[dict[str, Any]], latest_score: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "section_id": "risk_snapshot",
            "kind": "risk_snapshot",
            "title": "Risk Snapshot",
            "status": "complete",
            "provenance": ["model_derived", "deterministic"],
            "markdown": (
                f"{company['company_name']} scored {model_output['engine_score_0_100']:.2f}/100 "
                f"with decision bucket {model_output['decision_bucket']}. "
                f"Benchmark score: {model_output['audit_score_0_100']:.2f}/100."
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


def _apply_llm_synthesis(result: dict[str, Any], latest_score: dict[str, Any] | None = None, *, progress_callback=None) -> dict[str, Any]:
    from gemini_report_extractor import generate_report_sections_with_gemini

    score_context = latest_score or {}
    supplementary = _supplementary_ratios_from_extractions(result["extractions"])
    context = {
        "company": result["company"],
        "reporting_context": result.get("reporting_context", {}),
        "model_output": _public_model_context(result["model_output"]),
        "benchmark_output": result["benchmark_output"],
        "features": result["features"],
        "supplementary_ratios": supplementary,
        "field_snapshot": _field_snapshot(result["extractions"]),
        "risk_observations": _risk_observations(result["features"], supplementary, result["model_output"]),
        "extractions": _compact_extractions(result["extractions"]),
        "validation_issues": result["validation_issues"],
        "support_summary": score_context.get("support_summary") or result.get("decision", {}).get("final_statement"),
        "rule_flags_triggered": score_context.get("rule_flags_triggered"),
        "ratio_standards": {
            "current_ratio": "1.5-3.0 often healthy; below 1.0 can indicate liquidity pressure.",
            "cash_ratio": "0.5-1.0 often acceptable by sector; below 0.5 can be risky.",
            "ebitda_to_interest": "2.0+ more comfortable; below 1.5 weak.",
            "debt_to_assets": "Above 1.0 means debt exceeds assets; above 0.5 needs peer check.",
            "roa": "5% often acceptable and 20%+ very strong, but industry matters.",
            "cfo_to_ebitda": "Internal convention: near 1.0 implies strong cash conversion.",
        },
    }
    synthesis = generate_report_sections_with_gemini(context, progress_callback=progress_callback)
    allowed_kinds = {
        "company_profile",
        "model_verdict",
        "balance_sheet_risk",
        "liquidity_cash_flow",
        "profitability_asset_quality",
        "governance_audit",
        "key_red_flags",
        "what_could_change_view",
        "analyst_conclusion",
    }
    sections: list[dict[str, Any]] = []
    for raw_section in synthesis.get("sections", []) or []:
        if not isinstance(raw_section, dict):
            continue
        section_id = str(raw_section.get("section_id") or "").strip()
        if section_id not in allowed_kinds:
            continue
        section_ref_fields = {
            "company_profile": {"company_name", "cin", "financial_year", "revenue", "total_assets", "total_borrowings", "total_equity"},
            "model_verdict": {"revenue", "pat", "total_assets", "total_borrowings"},
            "balance_sheet_risk": {"total_assets", "total_borrowings", "total_equity", "retained_earnings"},
            "liquidity_cash_flow": {"cfo", "net_cash_change", "current_assets", "current_liabilities", "cash_and_equivalents", "interest_expense", "ebitda"},
            "profitability_asset_quality": {"revenue", "pat", "ebitda", "total_assets"},
            "governance_audit": {"opinion_type", "auditor_name", "promoter_holding_pct", "contingent_liabilities_amount", "emphasis_of_matter", "going_concern_uncertainty", "fraud_reported"},
            "key_red_flags": {"opinion_type", "auditor_name", "cfo", "ebitda", "current_assets", "current_liabilities", "contingent_liabilities_amount", "going_concern_uncertainty"},
            "what_could_change_view": {"cfo", "ebitda", "current_assets", "current_liabilities", "opinion_type", "contingent_liabilities_amount"},
            "analyst_conclusion": {"revenue", "pat", "ebitda", "cfo", "total_assets", "total_borrowings", "contingent_liabilities_amount"},
        }.get(section_id, set())
        sections.append(
            {
                "section_id": section_id,
                "kind": section_id,
                "title": str(raw_section.get("title") or section_id.replace("_", " ").title()),
                "status": "complete",
                "provenance": ["llm_synthesized", "model_derived", "source_grounded"],
                "markdown": str(raw_section.get("markdown") or ""),
                "data": {"structured_context": context if section_id == "risk_snapshot" else {}},
                "source_refs": _field_source_refs(result["extractions"], section_ref_fields),
                "warnings": list(raw_section.get("warnings") or []),
            }
        )
    if sections:
        result["sections"] = sections

    final_statement = str(synthesis.get("final_statement") or "").strip()
    confidence_statement = str(synthesis.get("confidence_statement") or "").strip()
    warnings = [str(item) for item in synthesis.get("warnings", []) or [] if str(item).strip()]
    if final_statement and result.get("decision"):
        result["decision"]["final_statement"] = final_statement
    if confidence_statement and result.get("decision"):
        result["decision"]["confidence_statement"] = confidence_statement
    if warnings and result.get("decision"):
        result["decision"]["warnings"] = list(dict.fromkeys([*result["decision"].get("warnings", []), *warnings]))
    return result


def _build_scored_result(job: dict[str, Any], extraction_payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
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
            "Uploaded report was scored through the primary risk score and benchmark score stack.",
            "Sector may be 'Unknown' if the annual report did not disclose a clean business category.",
        ],
    }
    extractions = _contract_extractions(job_id, extraction_payload)
    reporting_context = _reporting_context(extraction_payload, extractions)
    validation_issues = _validation_issues(extraction_payload, job_id)
    features = _feature_values(raw_df)
    sections = _fallback_sections(company, model_output, features, latest_score)
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
    result = {
        "job_id": job_id,
        "status": "completed",
        "company": company,
        "reporting_context": reporting_context,
        "extractions": extractions,
        "validation_issues": validation_issues,
        "features": features,
        "model_output": model_output,
        "benchmark_output": benchmark_output,
        "sections": sections,
        "decision": decision,
    }
    return result, latest_score


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
        result, latest_score = _build_scored_result(job, extraction_payload)

        update_job(job_id, status="generating", progress_pct=92, current_stage="generating_analyst_report", message="Generating grounded analyst report.")
        try:
            result = _apply_llm_synthesis(
                result,
                latest_score,
                progress_callback=lambda message: (
                    log_job(job_id, message),
                    append_event(job_id, "job.progress", {"current_stage": "generating_analyst_report", "message": message}),
                ),
            )
        except Exception as synthesis_exc:  # noqa: BLE001
            message = f"LLM report synthesis failed; using deterministic fallback sections. {synthesis_exc}"
            log_job(job_id, message)
            result.setdefault("validation_issues", []).append(
                {
                    "field": None,
                    "severity": "watch",
                    "message": message,
                    "source_refs": [],
                }
            )
            if result.get("decision"):
                result["decision"].setdefault("warnings", []).append(message)

        update_job(job_id, status="generating", progress_pct=96, current_stage="assembling_report", message="Assembling final report package.")
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
