#!/usr/bin/env python3
"""
Resolve CIN (Corporate Identification Number) for companies by searching MCA "Find CIN" page.

Reads a CSV with company_name (and optional cin). For each row without CIN, opens
MCA Find CIN (findCinFinalSingleCom.html), searches by company name, and fills CIN
from the first/best result. Requires manual CAPTCHA entry (browser pauses).

Usage:
  python scripts/cin_resolver.py --input data/cibil/wilful_defaulters_50.csv --output data/cibil/wilful_defaulters_50_with_cin.csv
  python scripts/cin_resolver.py --input data/cibil/non_defaulters_50.csv --output data/cibil/non_defaulters_50_with_cin.csv --limit 5

Checkpoint: data/mca/cin_resolver_checkpoint.csv (company_name -> cin) so you can resume.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from pathlib import Path
from typing import Optional

# Allow running from project root
_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from cibil_loader import load_cibil_csv

MCA_FIND_CIN_URL = "https://www.mca.gov.in/content/mca/global/en/mca/fo-llp-services/findCinFinalSingleCom.html"
CHECKPOINT_PATH = Path(__file__).resolve().parent.parent / "data" / "mca" / "cin_resolver_checkpoint.csv"
CIN_PATTERN = re.compile(r"^[A-Z]{1,2}[0-9]{2}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$", re.IGNORECASE)
DEFAULT_DELAY_SECONDS = 25  # MCA rate limit ~100–150/hour


def load_checkpoint(path: Path) -> dict[str, str]:
    """Load company_name -> cin from checkpoint CSV."""
    if not path.exists():
        return {}
    out = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = (row.get("company_name") or "").strip()
            cin = (row.get("cin") or "").strip()
            if name and cin:
                out[name] = cin
    return out


def save_checkpoint_row(path: Path, company_name: str, cin: str) -> None:
    """Append one row to checkpoint CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["company_name", "cin"])
        w.writerow([company_name, cin])


def resolve_cin_mca(company_name: str, *, headless: bool = False, delay_seconds: float = DEFAULT_DELAY_SECONDS) -> Optional[str]:
    """
    Search MCA Find CIN by company name; return CIN from first result or None.
    Pauses for manual CAPTCHA unless headless (then returns None).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed. Run: pip install playwright && playwright install chromium", file=sys.stderr)
        return None

    # Use first 4–5 words to avoid "no data found" from long names; min 3 chars required by MCA
    search_name = " ".join((company_name or "").strip().split()[:6])
    if len(search_name) < 3:
        search_name = company_name[:50] if company_name else ""

    cin_found: Optional[str] = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            page.goto(MCA_FIND_CIN_URL, wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)

            # Select "Company" (entity type)
            try:
                page.select_option("select#entityType", "Company")
            except Exception:
                try:
                    page.locator("text=Company").first.click()
                except Exception:
                    pass
            time.sleep(0.5)

            # Select "Search Based on existing Company/LLP Name"
            try:
                page.get_by_label("Search Based on existing Company/LLP Name", exact=False).check()
            except Exception:
                try:
                    page.locator("input[value*='existing'][value*='Name']").check()
                except Exception:
                    page.locator("text=Search Based on existing").first.click()
            time.sleep(0.5)

            # Match type: "Contains anywhere"
            try:
                page.select_option("select#matchType", "Contains anywhere")
            except Exception:
                try:
                    page.locator("select").filter(has_text="Contains").select_option(label="Contains anywhere")
                except Exception:
                    pass

            # Company name input – common possible names
            for selector in ['input[name*="companyName"]', 'input[name*="existingName"]', 'input[id*="companyName"]', 'input[placeholder*="Name"]', 'input[type="text"]']:
                try:
                    inp = page.locator(selector).first
                    if inp.count() and inp.is_visible():
                        inp.fill(search_name)
                        break
                except Exception:
                    continue

            if not headless:
                print("\n>>> Solve CAPTCHA in the browser, then press Enter here to continue...")
                input()

            # Submit
            try:
                page.get_by_role("button", name="Submit").click()
            except Exception:
                try:
                    page.locator("input[type='submit'][value*='Submit']").click()
                except Exception:
                    page.locator("button:has-text('Submit')").click()
            time.sleep(3)

            # Parse result table for CIN/LLPIN
            body = page.inner_text("body")
            # CIN format: L27xxx... or U27xxx...
            for m in CIN_PATTERN.finditer(body):
                cand = m.group(0)
                if cand not in ("", "CIN/LLPIN"):
                    cin_found = cand.upper()
                    break

            # Alternative: look for table cell with CIN
            if not cin_found:
                try:
                    cells = page.locator("table td").all_inner_texts()
                    for t in cells:
                        t = (t or "").strip()
                        if CIN_PATTERN.match(t):
                            cin_found = t.upper()
                            break
                except Exception:
                    pass

        except Exception as e:
            print(f"[error] {company_name}: {e}", file=sys.stderr)
        finally:
            try:
                browser.close()
            except Exception:
                pass

    if delay_seconds > 0:
        time.sleep(delay_seconds)
    return cin_found


def run_resolver(
    input_path: Path,
    output_path: Path,
    checkpoint_path: Path = CHECKPOINT_PATH,
    limit: Optional[int] = None,
    headless: bool = False,
    company_column: Optional[str] = None,
    cin_column: Optional[str] = None,
) -> None:
    """Load CSV, resolve CIN for rows missing it, write output CSV with CIN filled."""
    import pandas as pd

    raw_df = pd.read_csv(input_path, encoding="utf-8", dtype=str).fillna("")
    checkpoint = load_checkpoint(checkpoint_path)

    name_col = company_column or ("company_name" if "company_name" in raw_df.columns else raw_df.columns[0])
    cin_col = cin_column or ("cin" if "cin" in raw_df.columns else "cin")
    if cin_col not in raw_df.columns:
        raw_df[cin_col] = ""

    todo = []
    for i, row in raw_df.iterrows():
        name = (row.get(name_col) or "").strip()
        if not name:
            continue
        existing_cin = (row.get(cin_col) or "").strip()
        if existing_cin and CIN_PATTERN.match(existing_cin):
            continue
        if name in checkpoint:
            raw_df.at[i, cin_col] = checkpoint[name]
            continue
        todo.append((i, name))

    if limit is not None:
        todo = todo[:limit]

    total = len(todo)
    if total == 0:
        print("No companies need CIN resolution (all have CIN or are in checkpoint).")
        raw_df.to_csv(output_path, index=False)
        print(f"Wrote {output_path}")
        return

    print(f"Resolving CIN for {total} companies (MCA Find CIN; solve CAPTCHA when prompted)...")
    for idx, (i, name) in enumerate(todo, 1):
        print(f"[{idx}/{total}] {name[:50]}...")
        cin = resolve_cin_mca(name, headless=headless)
        if cin:
            raw_df.at[i, cin_col] = cin
            save_checkpoint_row(checkpoint_path, name, cin)
            checkpoint[name] = cin
            print(f"  -> {cin}")
        else:
            print("  -> (not found or CAPTCHA skipped)")

    raw_df.to_csv(output_path, index=False)
    print(f"Wrote {output_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Resolve CIN for companies via MCA Find CIN search")
    ap.add_argument("--input", "-i", type=Path, required=True, help="Input CSV with company_name column")
    ap.add_argument("--output", "-o", type=Path, required=True, help="Output CSV with CIN column filled")
    ap.add_argument("--checkpoint", type=Path, default=CHECKPOINT_PATH, help="Checkpoint CSV path")
    ap.add_argument("--limit", "-n", type=int, default=None, help="Max number of companies to resolve this run")
    ap.add_argument("--headless", action="store_true", help="Run headless (CAPTCHA will fail; use for testing)")
    ap.add_argument("--company-column", default=None, help="Override company name column")
    ap.add_argument("--cin-column", default=None, help="Override CIN column")
    args = ap.parse_args()

    run_resolver(
        args.input,
        args.output,
        checkpoint_path=args.checkpoint,
        limit=args.limit,
        headless=args.headless,
        company_column=args.company_column,
        cin_column=args.cin_column,
    )


if __name__ == "__main__":
    main()
