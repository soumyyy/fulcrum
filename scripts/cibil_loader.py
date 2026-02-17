#!/usr/bin/env python3
"""
Load and normalize company list from CIBIL (TransUnion CIBIL) or similar CSV export.

Expected input: CSV with at least company name; CIN (Corporate Identification Number)
optional. Column names are flexible and mapped via ALIASES.

Output: DataFrame with normalized columns [company_name, cin, source_row] for
downstream MCA fetch. Rows without CIN can be resolved later via MCA search.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

# Map common CIBIL/export column names to our canonical names.
COLUMN_ALIASES: Dict[str, str] = {
    "company name": "company_name",
    "company_name": "company_name",
    "borrower name": "company_name",
    "borrower": "company_name",
    "name of borrower": "company_name",
    "name": "company_name",
    "cin": "cin",
    "corporate identification number": "cin",
    "company registration number": "cin",
    "registration number": "cin",
    "company id": "cin",
}

REQUIRED_COLUMNS = ("company_name",)
CIN_PATTERN = re.compile(r"^[A-Z]{1,2}[0-9]{2}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$", re.IGNORECASE)


def normalize_column_name(raw: str) -> str:
    """Map raw header to canonical name."""
    key = (raw or "").strip().lower()
    return COLUMN_ALIASES.get(key, key)


def normalize_cin(value: Any) -> Optional[str]:
    """Validate and normalize CIN. Returns None if missing or invalid."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip().upper()
    if not s or s in ("NAN", "NA", "-", ""):
        return None
    # Remove spaces; CIN is 21 chars, no spaces
    s = s.replace(" ", "")
    if CIN_PATTERN.match(s):
        return s
    # Allow 21-char alphanumeric as best-effort
    if len(s) == 21 and s.isalnum():
        return s
    return None


def normalize_company_name(value: Any) -> str:
    """Clean company name for display and matching."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip() or ""


def load_cibil_csv(
    path: str | Path,
    company_name_column: Optional[str] = None,
    cin_column: Optional[str] = None,
    encoding: str = "utf-8",
) -> pd.DataFrame:
    """
    Load CSV from CIBIL (or similar) export and normalize to company_name + cin.

    If company_name_column or cin_column are provided, they override auto-detection
    via COLUMN_ALIASES. Encoding is tried as utf-8 first, then latin-1 on failure.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CIBIL input file not found: {path}")

    try:
        df = pd.read_csv(path, encoding=encoding, dtype=str)
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="latin-1", dtype=str)

    df = df.replace({None: "", "nan": "", "NaN": ""}).fillna("")

    # Resolve canonical column names
    name_col = company_name_column
    cin_col = cin_column

    if not name_col:
        for raw in df.columns:
            canonical = normalize_column_name(raw)
            if canonical == "company_name":
                name_col = raw
                break
    if not name_col:
        raise ValueError(
            f"No company name column found. Columns: {list(df.columns)}. "
            "Expected one of: " + ", ".join(k for k, v in COLUMN_ALIASES.items() if v == "company_name")
        )

    if not cin_col:
        for raw in df.columns:
            canonical = normalize_column_name(raw)
            if canonical == "cin":
                cin_col = raw
                break

    out = pd.DataFrame()
    out["company_name"] = df[name_col].map(normalize_company_name)
    out["cin"] = df[cin_col].map(normalize_cin) if cin_col else None
    out["source_row"] = range(len(df))

    # Drop rows with no company name
    out = out[out["company_name"].str.len() > 0].copy()
    out.reset_index(drop=True, inplace=True)

    return out


def get_rows_with_cin(df: pd.DataFrame) -> pd.DataFrame:
    """Return subset of rows that have a valid CIN (ready for MCA fetch)."""
    return df[df["cin"].notna()].copy()


def get_rows_missing_cin(df: pd.DataFrame) -> pd.DataFrame:
    """Return subset of rows without CIN (would need CIN resolution step)."""
    return df[df["cin"].isna()].copy()


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Load CIBIL CSV and normalize to company_name + CIN")
    ap.add_argument("input", type=Path, help="Path to CIBIL/company list CSV")
    ap.add_argument("--company-column", default=None, help="Override company name column")
    ap.add_argument("--cin-column", default=None, help="Override CIN column")
    ap.add_argument("--output", "-o", type=Path, default=None, help="Write normalized CSV here")
    ap.add_argument("--encoding", default="utf-8", help="CSV encoding")
    args = ap.parse_args()

    df = load_cibil_csv(
        args.input,
        company_name_column=args.company_column,
        cin_column=args.cin_column,
        encoding=args.encoding,
    )
    with_cin = get_rows_with_cin(df)
    missing_cin = get_rows_missing_cin(df)
    print(f"Total rows: {len(df)}")
    print(f"With CIN (ready for MCA): {len(with_cin)}")
    print(f"Missing CIN: {len(missing_cin)}")

    if args.output:
        df.to_csv(args.output, index=False)
        print(f"Wrote normalized list to {args.output}")
    else:
        print(df.to_string())
