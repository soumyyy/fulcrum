#!/usr/bin/env python3
"""
Process annual report PDFs in data/raw/reports/ using reports_manifest.csv.
Extracts P&L, Balance Sheet, Cash Flow, auditor report, notes, shareholding
and writes one row per PDF to data/processed/raw_feature_input.csv.

Usage:
  python scripts/process_reports_to_features.py [--reports-dir DATA/raw/reports] [--manifest MANIFEST] [--out OUT.csv]
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("pip install pdfplumber", file=sys.stderr)
    raise

# Default paths (project root = parent of scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "data" / "raw" / "reports"
DEFAULT_MANIFEST = DEFAULT_REPORTS_DIR / "reports_manifest.csv"
DEFAULT_OUT = PROJECT_ROOT / "data" / "processed" / "raw_feature_input.csv"

# Column order matching manual_feature_input_template.csv
RAW_COLUMNS = [
    "company_name", "cin", "financial_year", "cohort", "sector",
    "revenue", "pat", "interest_expense", "depreciation", "tax_expense", "ebitda",
    "total_equity", "total_borrowings", "current_assets", "current_liabilities", "total_assets",
    "cash_and_equivalents", "inventory", "receivables", "retained_earnings",
    "cfo", "cfi", "cff", "net_cash_change", "capex",
    "opinion_type", "going_concern_uncertainty", "emphasis_of_matter", "fraud_reported", "auditor_name",
    "related_party_transactions_amount", "contingent_liabilities_amount", "rpt_count", "pending_legal_cases_count",
    "promoter_holding_pct",
]


def _normalize_label(s: str) -> str:
    if not s or not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", s.lower().strip())


def _parse_amount(v) -> str | None:
    """Return string suitable for CSV (empty or number)."""
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        return "" if (v != v) else str(v)  # NaN check
    s = str(v).strip().replace(",", "")
    # Remove parentheses for negative
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    if not s or s in ("-", "—", "–", "NA", "N/A", ""):
        return ""
    try:
        float(s)
        return s
    except ValueError:
        return ""


def _find_amount_in_row(row: list, label_patterns: list[str]) -> str | None:
    """Row is list of cells; first cell(s) may be label, last often amount. Match label by patterns."""
    label = _normalize_label(str(row[0]) if row else "")
    if not any(p in label for p in label_patterns):
        return None
    # Prefer last column that looks like a number
    for i in range(len(row) - 1, -1, -1):
        a = _parse_amount(row[i])
        if a:
            return a
    return None


def _find_in_tables(tables: list, label_patterns: list[str], amount_scale: float = 1.0) -> str:
    """Search all tables for a line matching label_patterns; return amount string or empty."""
    for table in tables:
        for row in table:
            if not row:
                continue
            amt = _find_amount_in_row(row, label_patterns)
            if amt:
                try:
                    return str(float(amt) * amount_scale)
                except ValueError:
                    return amt
    return ""


def _extract_from_text(text: str, pattern: re.Pattern, group: int = 1) -> str:
    m = pattern.search(text)
    if m and m.lastindex >= group:
        return (m.group(group) or "").strip()
    return ""


def _extract_auditor_flags(text: str) -> dict:
    t = text.lower()
    opinion = "unqualified"
    if "disclaimer of opinion" in t or "disclaimer" in t and "opinion" in t:
        opinion = "disclaimer"
    elif "adverse opinion" in t or "adverse" in t and "opinion" in t:
        opinion = "adverse"
    elif "qualified opinion" in t or "qualified" in t and "opinion" in t:
        opinion = "qualified"
    going_concern = 1 if ("going concern" in t and ("material uncertainty" in t or "significant uncertainty" in t)) else 0
    emphasis = 1 if ("emphasis of matter" in t or "emphasis of matter paragraph" in t) else 0
    fraud = 1 if ("fraud" in t and ("reported" in t or "reporting" in t or "regulator" in t)) else 0
    auditor_name = ""
    for m in re.finditer(r"(?:audit(or|ors?)|statutory audit(or|ors?))\s*(?:report)?\s*[:\s]*([A-Za-z0-9\s,&.-]+?)(?:\s*for\s|$|\n)", text, re.I):
        name = (m.group(3) or "").strip()
        if len(name) > 3 and len(name) < 120:
            auditor_name = name
            break
    if not auditor_name:
        m = re.search(r"(?:M/s?\.?|M/s)\s*([A-Za-z0-9\s,&.-]+?)(?:\s*,?\s*(?:Chartered Accountants|CA)|\.|$)", text, re.I)
        if m:
            auditor_name = m.group(1).strip()
    return {
        "opinion_type": opinion,
        "going_concern_uncertainty": going_concern,
        "emphasis_of_matter": emphasis,
        "fraud_reported": fraud,
        "auditor_name": auditor_name[:200] if auditor_name else "",
    }


def _extract_promoter_pct(text: str) -> str:
    # Look for "Promoter" and a percentage nearby (e.g. "Promoter ... 45.20" or "45.20 %")
    for m in re.finditer(r"promoter[s]?\s*(?:and\s+group)?\s*[:\s]*([0-9]+\.?[0-9]*)\s*%?", text, re.I):
        return m.group(1).strip()
    for m in re.finditer(r"([0-9]+\.?[0-9]*)\s*%\s*(?:.*?\s)?promoter", text, re.I):
        return m.group(1).strip()
    return ""


def _extract_rpt_amount(text: str) -> str:
    for m in re.finditer(r"(?:related\s+party|rpt).*?(?:amount|rs\.?|inr)\s*[:\s]*([0-9,]+\.?[0-9]*)", text, re.I):
        return m.group(1).replace(",", "").strip()
    for m in re.finditer(r"([0-9,]+\.?[0-9]*)\s*(?:crore|cr\.?)\s*(?:.*?\s)?related\s+party", text, re.I):
        return m.group(1).replace(",", "").strip()
    return ""


def _extract_contingent_amount(text: str) -> str:
    for m in re.finditer(r"contingent\s+liab(?:ility|ilities).*?(?:rs\.?|inr|amount)\s*[:\s]*([0-9,]+\.?[0-9]*)", text, re.I):
        return m.group(1).replace(",", "").strip()
    for m in re.finditer(r"([0-9,]+\.?[0-9]*)\s*(?:crore|cr\.?)\s*(?:.*?\s)?contingent", text, re.I):
        return m.group(1).replace(",", "").strip()
    return ""


def extract_from_pdf(pdf_path: Path) -> dict:
    """Extract all raw feature inputs from one PDF. Returns dict of column -> value (str or number)."""
    out: dict[str, str | int] = {c: "" for c in RAW_COLUMNS}

    with pdfplumber.open(pdf_path) as pdf:
        all_text_parts = []
        all_tables = []
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_text_parts.append(text)
            tables = page.extract_tables()
            if tables:
                all_tables.extend(tables)

    full_text = "\n".join(all_text_parts)

    # P&L
    out["revenue"] = _find_in_tables(all_tables, ["revenue", "income from operations", "total income", "turnover"])
    out["pat"] = _find_in_tables(all_tables, ["profit after tax", "net profit", "pat", "profit for the period"])
    out["interest_expense"] = _find_in_tables(all_tables, ["interest", "finance cost", "finance costs", "interest expense"])
    out["depreciation"] = _find_in_tables(all_tables, ["depreciation", "depreciation and amortisation"])
    out["tax_expense"] = _find_in_tables(all_tables, ["tax", "income tax", "provision for tax", "tax expense"])
    out["ebitda"] = _find_in_tables(all_tables, ["ebitda"])

    # Balance sheet
    out["total_equity"] = _find_in_tables(all_tables, ["total equity", "net worth", "shareholders' funds", "equity", "share capital and reserves"])
    out["total_borrowings"] = _find_in_tables(all_tables, ["borrowings", "total debt", "long-term borrowings", "short-term borrowings"])
    out["current_assets"] = _find_in_tables(all_tables, ["current assets", "total current assets"])
    out["current_liabilities"] = _find_in_tables(all_tables, ["current liabilities", "total current liabilities"])
    out["total_assets"] = _find_in_tables(all_tables, ["total assets", "total non-current and current assets"])
    out["cash_and_equivalents"] = _find_in_tables(all_tables, ["cash and cash equivalents", "cash and bank", "cash "])
    out["inventory"] = _find_in_tables(all_tables, ["inventories", "inventory"])
    out["receivables"] = _find_in_tables(all_tables, ["trade receivables", "sundry debtors", "receivables", "accounts receivable"])
    out["retained_earnings"] = _find_in_tables(all_tables, ["retained earnings", "reserves and surplus", "reserves"])

    # Cash flow
    out["cfo"] = _find_in_tables(all_tables, ["operating activities", "cash from operating", "net cash from operating"])
    out["cfi"] = _find_in_tables(all_tables, ["investing activities", "cash from investing", "net cash from investing"])
    out["cff"] = _find_in_tables(all_tables, ["financing activities", "cash from financing", "net cash from financing"])
    out["net_cash_change"] = _find_in_tables(all_tables, ["net increase", "net decrease", "net change in cash", "cash and cash equivalents"])
    out["capex"] = _find_in_tables(all_tables, ["purchase of fixed assets", "purchase of property", "capital expenditure"])

    # Auditor
    auditor = _extract_auditor_flags(full_text)
    out["opinion_type"] = auditor["opinion_type"]
    out["going_concern_uncertainty"] = str(auditor["going_concern_uncertainty"])
    out["emphasis_of_matter"] = str(auditor["emphasis_of_matter"])
    out["fraud_reported"] = str(auditor["fraud_reported"])
    out["auditor_name"] = auditor["auditor_name"]

    # Notes
    out["related_party_transactions_amount"] = _extract_rpt_amount(full_text)
    out["contingent_liabilities_amount"] = _extract_contingent_amount(full_text)
    # rpt_count, pending_legal_cases_count: leave blank unless we add more parsing
    out["promoter_holding_pct"] = _extract_promoter_pct(full_text)

    return out


def load_manifest(manifest_path: Path) -> list[dict]:
    rows = []
    with open(manifest_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            if not row.get("filename") or not row.get("company_name"):
                continue
            rows.append(row)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract feature inputs from annual report PDFs")
    ap.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR, help="Directory containing PDFs")
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="CSV: filename, company_name, cin, financial_year, cohort, sector")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output CSV (raw feature rows)")
    ap.add_argument("--append", action="store_true", help="Append to existing out file (default: overwrite)")
    args = ap.parse_args()

    if not args.manifest.exists():
        print(f"Manifest not found: {args.manifest}", file=sys.stderr)
        print("Add rows to data/raw/reports/reports_manifest.csv (filename, company_name, cin, financial_year, cohort, sector).", file=sys.stderr)
        sys.exit(1)

    manifest_rows = load_manifest(args.manifest)
    if not manifest_rows:
        print("No rows in manifest (need filename and company_name).", file=sys.stderr)
        sys.exit(1)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.append else "w"
    write_header = not (args.append and args.out.exists())

    for m in manifest_rows:
        fname = m.get("filename", "").strip()
        pdf_path = args.reports_dir / fname
        if not pdf_path.exists():
            print(f"Skip (file not found): {fname}", file=sys.stderr)
            continue
        try:
            row = extract_from_pdf(pdf_path)
        except Exception as e:
            print(f"Error processing {fname}: {e}", file=sys.stderr)
            continue
        row["company_name"] = m.get("company_name", "")
        row["cin"] = m.get("cin", "")
        row["financial_year"] = m.get("financial_year", "")
        row["cohort"] = m.get("cohort", "")
        row["sector"] = m.get("sector", "")

        with open(args.out, mode, newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=RAW_COLUMNS, extrasaction="ignore")
            if write_header:
                w.writeheader()
                write_header = False
            w.writerow(row)
        print(f"Wrote row: {m.get('company_name')} FY {m.get('financial_year')} -> {args.out}")

    if write_header:
        # No file was written; write header only so file exists
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=RAW_COLUMNS).writeheader()
        print(f"No PDFs processed; empty file written: {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
