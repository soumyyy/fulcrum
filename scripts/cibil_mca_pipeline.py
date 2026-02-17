#!/usr/bin/env python3
"""
Pipeline: CIBIL data → CIN → MCA report.

  1. Load company list from CIBIL CSV (columns: company name, optional CIN).
  2. For each row with CIN: fetch report from MCA portal and save under data/mca/reports/{cin}/.
  3. Checkpoint progress so runs can resume after interruptions.

Usage:
  python scripts/cibil_mca_pipeline.py run --input data/cibil/companies.csv
  python scripts/cibil_mca_pipeline.py run --input data/cibil/companies.csv --limit 5
  python scripts/cibil_mca_pipeline.py status --input data/cibil/companies.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Optional

# Allow running from project root: python scripts/cibil_mca_pipeline.py
_scripts_dir = Path(__file__).resolve().parent
if _scripts_dir not in (Path(p).resolve() for p in sys.path):
    sys.path.insert(0, str(_scripts_dir))

from cibil_loader import get_rows_with_cin, load_cibil_csv
from mca_fetcher import mca_fetch_report

# Paths relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CIBIL_INPUT = PROJECT_ROOT / "data" / "cibil" / "companies.csv"
DEFAULT_CHECKPOINT = PROJECT_ROOT / "data" / "mca" / "pipeline_checkpoint.csv"
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "data" / "mca" / "reports"


def load_checkpoint(path: Path) -> set[str]:
    """Load set of CINs already processed (success)."""
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["cin"] for row in reader if row.get("status") == "success"}


def save_checkpoint_row(path: Path, cin: str, company_name: str, status: str, message: str = "") -> None:
    """Append one row to checkpoint CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["cin", "company_name", "status", "message"])
        w.writerow([cin, company_name, status, message])


def run_pipeline(
    input_path: Path,
    checkpoint_path: Path = DEFAULT_CHECKPOINT,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    limit: Optional[int] = None,
    headless: bool = False,
    company_name_column: Optional[str] = None,
    cin_column: Optional[str] = None,
) -> None:
    """Load CIBIL CSV, skip already-done CINs, fetch MCA report for each remaining."""
    df = load_cibil_csv(input_path, company_name_column=company_name_column, cin_column=cin_column)
    todo = get_rows_with_cin(df)
    if todo.empty:
        print("No rows with CIN found. Add a CIN column or use --company-column / --cin-column.")
        return

    done = load_checkpoint(checkpoint_path)
    todo = todo[~todo["cin"].isin(done)]
    if limit is not None:
        todo = todo.head(limit)

    total = len(todo)
    if total == 0:
        print("No new CINs to process (all already in checkpoint).")
        return

    print(f"Processing {total} companies (CINs not yet in checkpoint)...")
    for idx, (_, row) in enumerate(todo.iterrows(), start=1):
        cin = row["cin"]
        name = row["company_name"]
        print(f"[{idx}/{total}] CIN={cin} name={name[:50]}...")
        result = mca_fetch_report(cin, output_dir=reports_dir, headless=headless)
        status = "success" if result["success"] else "error"
        save_checkpoint_row(checkpoint_path, cin, name, status, result.get("message", "")[:500])
        if not result["success"]:
            print(f"  -> {result.get('message', '')}")


def status_pipeline(input_path: Path, checkpoint_path: Path = DEFAULT_CHECKPOINT) -> None:
    """Print how many CINs from input are done vs pending."""
    df = load_cibil_csv(input_path)
    with_cin = get_rows_with_cin(df)
    done = load_checkpoint(checkpoint_path)
    done_count = sum(1 for c in with_cin["cin"] if c in done)
    pending = len(with_cin) - done_count
    print(f"Input rows with CIN: {len(with_cin)}")
    print(f"Already processed (in checkpoint): {done_count}")
    print(f"Pending: {pending}")
    print(f"Checkpoint file: {checkpoint_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="CIBIL → CIN → MCA report pipeline")
    sub = ap.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run pipeline: load CIBIL CSV, fetch MCA for each CIN")
    run.add_argument("--input", "-i", type=Path, default=DEFAULT_CIBIL_INPUT, help="CIBIL/company list CSV")
    run.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT, help="Checkpoint CSV path")
    run.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR, help="Where to save MCA reports")
    run.add_argument("--limit", "-n", type=int, default=None, help="Max number of CINs to process this run")
    run.add_argument("--headless", action="store_true", help="Run browser headless")
    run.add_argument("--company-column", default=None, help="Override company name column name")
    run.add_argument("--cin-column", default=None, help="Override CIN column name")
    run.set_defaults(func=lambda a: run_pipeline(
        a.input, a.checkpoint, a.reports_dir, a.limit, a.headless, a.company_column, a.cin_column
    ))

    st = sub.add_parser("status", help="Show pipeline status (done vs pending)")
    st.add_argument("--input", "-i", type=Path, default=DEFAULT_CIBIL_INPUT, help="Same CSV as run --input")
    st.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT, help="Checkpoint CSV path")
    st.set_defaults(func=lambda a: status_pipeline(a.input, a.checkpoint))

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
