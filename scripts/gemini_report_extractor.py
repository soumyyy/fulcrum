#!/usr/bin/env python3
"""Gemini-backed annual-report extraction for Fulcrum report jobs.

The LLM is used only to extract source-grounded facts from PDFs. Normalization,
ratio calculation, model scoring, and decision logic stay deterministic in the
report runner.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import time
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
REQUIRED_TIER1A_RAW_FIELDS = [
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
]
OPTIONAL_CONTEXT_FIELDS = [
    "current_assets",
    "current_liabilities",
    "cash_and_equivalents",
    "inventory",
    "receivables",
    "capex",
    "opinion_type",
    "auditor_name",
    "contingent_liabilities_amount",
    "promoter_holding_pct",
    "emphasis_of_matter",
    "going_concern_uncertainty",
    "fraud_reported",
]


EXTRACTION_PROMPT = """
You are extracting accounting facts from an Indian annual report PDF for a credit-risk model.
Return ONLY valid JSON. Do not include markdown.

Use the standalone financial statements by default. If standalone is unavailable, use consolidated and set basis accordingly.
Extract latest financial year values only, unless a field explicitly requires an auditor/shareholding note.
Normalize all monetary normalized_value fields to INR crore. Preserve the raw value text in value.
If a value is not found, return null. Do not infer numbers. Do not calculate ratios.
Use negative signs for cash outflows when the report presents them as outflows.
For capex, use purchase of property, plant and equipment / fixed assets from cash flow, negative if cash outflow.
Infer sector from the annual report's business overview, revenue segments, director report, and company description.
Use the closest label from this taxonomy where possible: Cement, Engineering / Manufacturing, FMCG / Foods, FMCG / Foods / Agro, Gems & Jewellery, IT / Services, Infrastructure, Logistics, Media, Mining, NBFC / Leasing, Oil & Gas, Oil & Gas / Energy, Pharma, Real Estate, Shipbuilding, Steel & Metals, Textiles, Travel / Aviation, Travel / Aviation / Hospitality, Travel / Hospitality.

Return this exact JSON shape:
{
  "document": {
    "company_name": string | null,
    "cin": string | null,
    "financial_year": integer | null,
    "sector": string | null,
    "basis": "standalone" | "consolidated" | "unknown",
    "currency": "INR" | null,
    "scale_detected": string | null,
    "warnings": [string]
  },
  "fields": [
    {
      "field": string,
      "value": string | number | null,
      "normalized_value": number | string | null,
      "unit": string | null,
      "scale": string | null,
      "period": string | null,
      "basis": "standalone" | "consolidated" | "unknown",
      "confidence": number,
      "page": integer | null,
      "snippet": string | null,
      "warnings": [string]
    }
  ],
  "validation_notes": [
    {"field": string | null, "severity": "info" | "watch" | "warning" | "critical", "message": string}
  ]
}

Fields to extract:
- company_name
- cin
- financial_year
- revenue
- pat
- interest_expense
- tax_expense
- depreciation
- ebitda
- total_equity
- total_borrowings
- total_assets
- retained_earnings
- cfo
- cfi
- cff
- net_cash_change
- current_assets
- current_liabilities
- cash_and_equivalents
- inventory
- receivables
- capex
- opinion_type
- auditor_name
- contingent_liabilities_amount
- promoter_holding_pct
- emphasis_of_matter
- going_concern_uncertainty
- fraud_reported

Quality rules:
- Include source page and short source snippet for every non-null value where possible.
- For opinion_type, use one of: unqualified, qualified, adverse, disclaimer, unknown.
- For emphasis_of_matter, going_concern_uncertainty, and fraud_reported, return 1, 0, or null.
- For contingent_liabilities_amount, use quantified contingent liabilities only; exclude capital commitments unless clearly included in a printed contingent liabilities total.
- If there is ambiguity between standalone and consolidated, choose standalone and add a warning.
""".strip()


def _require_api_key() -> str:
    _load_local_env()
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Set it in the backend environment before uploading annual reports.")
    return api_key


def _load_local_env() -> None:
    """Load root .env without overriding real process environment variables."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        value = raw_value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _coerce_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("Gemini extraction did not return a JSON object")
    return payload


def _file_state_value(file_obj: Any) -> str:
    state = getattr(file_obj, "state", "")
    value = getattr(state, "value", state)
    return str(value).upper()


def extract_annual_report_with_gemini(
    pdf_path: Path,
    *,
    model: str | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Upload a PDF to Gemini and return a strict JSON extraction payload."""
    api_key = _require_api_key()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    from google import genai  # Imported lazily so the backend can boot without the optional package.
    from google.genai import types

    def emit(message: str) -> None:
        if progress_callback is not None:
            progress_callback(message)

    timeout_ms = int(os.environ.get("GEMINI_HTTP_TIMEOUT_MS", "900000"))
    emit(f"Initializing Gemini client with HTTP timeout {timeout_ms} ms.")
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=timeout_ms))
    model_name = model or os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)

    emit(f"Uploading PDF to Gemini Files API: {pdf_path.name} ({pdf_path.stat().st_size} bytes).")
    uploaded = client.files.upload(
        file=pdf_path,
        config=types.UploadFileConfig(mime_type="application/pdf", display_name=pdf_path.name),
    )
    emit(f"Gemini file uploaded: {getattr(uploaded, 'name', 'unknown')}. Waiting for file processing.")

    for attempt in range(90):
        state = _file_state_value(uploaded)
        if "FAILED" in state:
            raise RuntimeError(f"Gemini failed to process uploaded file: {state}")
        if "PROCESSING" not in state:
            emit(f"Gemini file processing state: {state or 'READY'} after {attempt} poll(s).")
            break
        time.sleep(2)
        if attempt % 5 == 0:
            emit(f"Gemini file is still processing ({attempt * 2}s elapsed).")
        uploaded = client.files.get(name=uploaded.name)
    else:
        raise TimeoutError("Timed out waiting for Gemini to process the uploaded PDF.")

    emit(f"Requesting structured extraction from {model_name}.")
    response = client.models.generate_content(
        model=model_name,
        contents=[uploaded, EXTRACTION_PROMPT],
        config=types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
        ),
    )
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini returned an empty extraction response")

    emit(f"Gemini returned extraction response with {len(text)} characters.")
    payload = _coerce_json(text)
    payload.setdefault("_meta", {})
    payload["_meta"].update(
        {
            "model": model_name,
            "uploaded_file_name": getattr(uploaded, "name", None),
            "uploaded_file_uri": getattr(uploaded, "uri", None),
        }
    )
    return payload


REPORT_SYNTHESIS_PROMPT = """
You are writing an expert credit-risk analyst memo from validated annual-report facts.
Return ONLY valid JSON. Do not include markdown fences.

Use only the structured input provided by the backend. Do not invent facts, peer data, dates, covenant terms, ratings, or auditor observations.
Be direct and analytical. The audience is an expert risk analyst.
Mention ratio values where relevant, and distinguish model-derived conclusions from extracted facts.
If extraction confidence or sector detection is weak, say so.

Return this exact JSON shape:
{
  "sections": [
    {
      "section_id": "company_profile" | "model_verdict" | "balance_sheet_risk" | "liquidity_cash_flow" | "profitability_asset_quality" | "governance_audit" | "key_red_flags" | "what_could_change_view" | "analyst_conclusion",
      "title": string,
      "markdown": string,
      "warnings": [string]
    }
  ],
  "final_statement": string,
  "confidence_statement": string,
  "warnings": [string]
}

Required sections:
- company_profile: identify company, reporting year, basis, sector status, scale, revenue, asset base, borrowings, equity, and main caveats.
- model_verdict: engine score, audit baseline score, decision bucket, model agreement/disagreement, and what the score should be used for.
- balance_sheet_risk: debt/assets, borrowings, equity buffer, retained earnings/assets, and whether leverage looks structurally risky.
- liquidity_cash_flow: current ratio, cash ratio, working capital/assets, CFO, CFO/assets, CFO/EBITDA, net cash change/assets, and EBITDA/interest.
- profitability_asset_quality: EBITDA margin, PAT margin, ROA, revenue, PAT, EBITDA, and whether profitability offsets the risk signals.
- governance_audit: audit opinion, auditor, emphasis/going-concern/fraud flags, promoter holding, contingent liabilities where available.
- key_red_flags: the 3-6 most important risks, each tied to a specific extracted fact, ratio, or model output.
- what_could_change_view: what an analyst should verify next, including missing evidence, sector uncertainty, cash conversion, audit qualifications, and liquidity quality.
- analyst_conclusion: final action-oriented statement for a risk-review queue.

Make the memo detailed enough to be useful without opening the ratio table:
- discuss asset scale, revenue, borrowings, equity, PAT, EBITDA, CFO, and net cash movement when present
- compare key ratios to the provided standards
- mention whether liquidity appears adequate or weak
- mention whether cash conversion supports or contradicts accounting profitability
- mention sector detection confidence and any model caveat
- use bullets where it improves scanability
- do not call the company a defaulter unless the provided model or source facts explicitly say so
- do not overstate sector percentiles when the benchmark context says they are computed from upload scope only
""".strip()


def generate_report_sections_with_gemini(
    structured_context: dict[str, Any],
    *,
    model: str | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Generate grounded analyst sections from already-extracted and scored facts."""
    api_key = _require_api_key()

    from google import genai
    from google.genai import types

    def emit(message: str) -> None:
        if progress_callback is not None:
            progress_callback(message)

    timeout_ms = int(os.environ.get("GEMINI_HTTP_TIMEOUT_MS", "900000"))
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=timeout_ms))
    model_name = model or os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    payload = {
        "instructions": REPORT_SYNTHESIS_PROMPT,
        "structured_context": structured_context,
    }
    emit(f"Requesting grounded analyst report generation from {model_name}.")
    response = client.models.generate_content(
        model=model_name,
        contents=json.dumps(payload, ensure_ascii=False),
        config=types.GenerateContentConfig(
            temperature=0.15,
            response_mime_type="application/json",
        ),
    )
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini returned an empty report synthesis response")
    emit(f"Gemini returned analyst report response with {len(text)} characters.")
    result = _coerce_json(text)
    result.setdefault("_meta", {})
    result["_meta"].update({"model": model_name})
    return result


def extracted_fields_by_name(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    fields = payload.get("fields", [])
    if not isinstance(fields, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for item in fields:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field", "")).strip()
        if field:
            out[field] = item
    return out


def numeric_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text == "":
        return None
    if text.lower() in {"null", "none", "n/a", "na", "not ascertainable"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if cleaned in {"", "-", "."}:
        return None
    try:
        number = float(cleaned)
    except ValueError:
        return None
    return -abs(number) if negative else number
