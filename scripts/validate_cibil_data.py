#!/usr/bin/env python3
"""
Validate wilful_defaulters_50.csv and non_defaulters_50.csv for the Fulcrum pipeline.

Checks:
- Row counts (50 each)
- Required columns present
- No duplicate company names
- CIN format (21-char, L-prefix for defaulters)
- Numeric columns where expected
- Sector consistency
- Loadable by cibil_loader / pipeline
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_CIBIL = PROJECT_ROOT / "data" / "cibil"

CIN_PATTERN = re.compile(r"^[A-Z]{1,2}[0-9]{2}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$", re.IGNORECASE)
VALID_DEFAULT_YEAR_RANGE = (2010, 2030)


def load_csv(path: Path) -> tuple[list[dict], list[str]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    return rows, fieldnames


def validate_defaulters(rows: list[dict], fieldnames: list[str]) -> list[str]:
    errors = []
    required = {"company_name", "cin", "amount_crore", "default_year", "fy_before_default", "sector"}
    missing_cols = required - set(fieldnames)
    if missing_cols:
        errors.append(f"Missing columns: {missing_cols}")

    if len(rows) != 50:
        errors.append(f"Expected 50 rows, got {len(rows)}")

    names = [r.get("company_name", "").strip() for r in rows]
    dupes = [n for n in names if names.count(n) > 1]
    if dupes:
        errors.append(f"Duplicate company_name(s): {list(set(dupes))}")

    for i, r in enumerate(rows):
        cin = (r.get("cin") or "").strip().replace(" ", "").upper()
        if not cin:
            errors.append(f"Row {i+2}: missing CIN for {r.get('company_name', '?')}")
        elif not CIN_PATTERN.match(cin):
            errors.append(f"Row {i+2}: invalid CIN format '{cin}' for {r.get('company_name', '?')}")
        elif not cin.startswith("L"):
            errors.append(f"Row {i+2}: CIN must be L (public limited), got '{cin[:1]}' for {r.get('company_name', '?')}")

        amt = r.get("amount_crore", "").strip()
        if amt and not (amt.replace(".", "").replace("-", "").isdigit()):
            errors.append(f"Row {i+2}: amount_crore not numeric: '{amt}'")

        dy = r.get("default_year", "").strip()
        if dy:
            try:
                y = int(dy)
                if y < VALID_DEFAULT_YEAR_RANGE[0] or y > VALID_DEFAULT_YEAR_RANGE[1]:
                    errors.append(f"Row {i+2}: default_year out of range: {y}")
            except ValueError:
                errors.append(f"Row {i+2}: default_year not integer: '{dy}'")

        sector = (r.get("sector") or "").strip()
        if not sector:
            errors.append(f"Row {i+2}: missing sector for {r.get('company_name', '?')}")

    return errors


def validate_non_defaulters(rows: list[dict], fieldnames: list[str]) -> list[str]:
    errors = []
    required = {"company_name", "cin", "sector"}
    missing_cols = required - set(fieldnames)
    if missing_cols:
        errors.append(f"Missing columns: {missing_cols}")

    if len(rows) != 50:
        errors.append(f"Expected 50 rows, got {len(rows)}")

    names = [r.get("company_name", "").strip() for r in rows]
    dupes = [n for n in names if names.count(n) > 1]
    if dupes:
        errors.append(f"Duplicate company_name(s): {list(set(dupes))}")

    for i, r in enumerate(rows):
        cin = (r.get("cin") or "").strip().replace(" ", "").upper()
        if not cin:
            errors.append(f"Row {i+2}: missing CIN for {r.get('company_name', '?')}")
        elif not CIN_PATTERN.match(cin):
            errors.append(f"Row {i+2}: invalid CIN format '{cin}' for {r.get('company_name', '?')}")

        sector = (r.get("sector") or "").strip()
        if not sector:
            errors.append(f"Row {i+2}: missing sector for {r.get('company_name', '?')}")

    return errors


def test_cibil_loader(path: Path) -> list[str]:
    """Ensure file is loadable by cibil_loader and has CINs for pipeline."""
    errors = []
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from cibil_loader import get_rows_with_cin, load_cibil_csv
        df = load_cibil_csv(path)
        with_cin = get_rows_with_cin(df)
        if len(with_cin) != len(df):
            errors.append(f"cibil_loader: only {len(with_cin)}/{len(df)} rows have valid CIN (pipeline needs CIN for MCA fetch)")
    except Exception as e:
        errors.append(f"cibil_loader failed: {e}")
    return errors


def main() -> int:
    def_path = DATA_CIBIL / "wilful_defaulters_50.csv"
    non_path = DATA_CIBIL / "non_defaulters_50.csv"

    all_errors = []

    for path, label in [(def_path, "wilful_defaulters_50.csv"), (non_path, "non_defaulters_50.csv")]:
        if not path.exists():
            all_errors.append(f"{label}: file not found at {path}")
            continue
        rows, fieldnames = load_csv(path)
        if label == "wilful_defaulters_50.csv":
            errs = validate_defaulters(rows, fieldnames)
        else:
            errs = validate_non_defaulters(rows, fieldnames)
        for e in errs:
            all_errors.append(f"{label}: {e}")
        loader_errs = test_cibil_loader(path)
        for e in loader_errs:
            all_errors.append(f"{label}: {e}")

    if all_errors:
        print("Validation FAILED:\n")
        for e in all_errors:
            print(f"  - {e}")
        return 1

    print("Validation passed.")
    print("  wilful_defaulters_50.csv: 50 rows, required columns, all CINs L and valid, no duplicates.")
    print("  non_defaulters_50.csv: 50 rows, required columns, all CINs valid, no duplicates.")
    print("  Both files loadable by cibil_loader and ready for CIN→MCA pipeline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
