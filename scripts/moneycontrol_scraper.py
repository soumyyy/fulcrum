#!/usr/bin/env python3
"""
Scrapes P&L, Balance Sheet, Cash Flow from Screener.in for all 100 companies.
Writes rows to data/processed/mc_scraped_features.csv
Checkpoints after each company; re-runnable (skips done companies).
"""
from __future__ import annotations

import csv
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WILFUL_PATH = PROJECT_ROOT / "data" / "cibil" / "wilful_defaulters_50.csv"
NON_DEFAULTER_PATH = PROJECT_ROOT / "data" / "cibil" / "non_defaulters_50.csv"
PLAN_PATH = PROJECT_ROOT / "data" / "processed" / "financial_download_plan.csv"
OUT_PATH = PROJECT_ROOT / "data" / "processed" / "mc_scraped_features.csv"
CHECKPOINT_PATH = PROJECT_ROOT / "data" / "processed" / "scrape_checkpoint.csv"
ERRORS_PATH = PROJECT_ROOT / "data" / "processed" / "scrape_errors.csv"

SCREENER_SEARCH = "https://www.screener.in/api/company/search/?q={query}"
SCREENER_COMPANY = "https://www.screener.in/company/{slug}/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.screener.in",
    "Accept": "text/html,application/xhtml+xml,application/json",
}

OUT_COLUMNS = [
    "company_name", "cin", "financial_year", "cohort", "sector",
    "revenue", "pat", "interest_expense", "depreciation", "tax_expense", "ebitda",
    "total_equity", "total_borrowings", "current_assets", "current_liabilities", "total_assets",
    "cash_and_equivalents", "inventory", "receivables", "retained_earnings",
    "cfo", "cfi", "cff", "net_cash_change", "capex",
    "opinion_type", "going_concern_uncertainty", "emphasis_of_matter", "fraud_reported", "auditor_name",
    "related_party_transactions_amount", "contingent_liabilities_amount", "rpt_count",
    "pending_legal_cases_count", "promoter_holding_pct",
]


# ── Utilities ──────────────────────────────────────────────────────────────────

def load_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ensure_csv(path: Path, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=fieldnames).writeheader()


def append_row(path: Path, fieldnames: list[str], row: dict) -> None:
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writerow(row)
        f.flush()


def load_checkpoint(path: Path) -> set[tuple[str, int]]:
    done: set[tuple[str, int]] = set()
    for row in load_csv_rows(path):
        cin = str(row.get("cin", "")).strip()
        fy_raw = str(row.get("financial_year", "")).strip()
        if cin and fy_raw:
            try:
                done.add((cin, int(float(fy_raw))))
            except ValueError:
                pass
    return done


def log_error(company_name, cin, year, cohort, slug, stage, message):
    ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    append_row(ERRORS_PATH,
        ["timestamp", "company_name", "cin", "financial_year", "cohort", "slug", "stage", "error"],
        {"timestamp": ts, "company_name": company_name, "cin": cin,
         "financial_year": str(year), "cohort": cohort, "slug": slug,
         "stage": stage, "error": str(message)[:1000]})


def fmt(v) -> str:
    return "" if v is None else str(v)


# ── Screener.in ────────────────────────────────────────────────────────────────

def search_screener(session: requests.Session, company_name: str) -> str | None:
    """Return Screener slug (e.g. 'GITANJALI') or None."""
    try:
        r = session.get(
            SCREENER_SEARCH.format(query=requests.utils.quote(company_name)),
            headers=HEADERS, timeout=15,
        )
        r.raise_for_status()
        results = r.json()
        if results:
            url = results[0].get("url", "")
            # url like /company/GITANJALI/consolidated/ or /company/GITANJALI/
            m = re.search(r"/company/([^/]+)/", url)
            if m:
                return m.group(1)
    except Exception as exc:
        print(f"  Search error for '{company_name}': {exc}")
    return None


def fetch_company_page(session: requests.Session, slug: str) -> BeautifulSoup | None:
    try:
        r = session.get(SCREENER_COMPANY.format(slug=slug), headers=HEADERS, timeout=20)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except Exception as exc:
        print(f"  Fetch error for slug '{slug}': {exc}")
        return None


# ── Table parsing ──────────────────────────────────────────────────────────────

def parse_screener_table(soup: BeautifulSoup, section_id: str) -> dict[str, dict[int, float]]:
    """
    Returns {row_label: {year: value}} for a given section id like
    'profit-loss', 'balance-sheet', 'cash-flow'.
    Screener renders tables with class 'data-table'.
    Years are in <th> elements like 'Mar 2017'.
    """
    section = soup.find(id=section_id)
    if section is None:
        return {}

    table = section.find("table", class_="data-table")
    if table is None:
        # Try any table inside
        table = section.find("table")
    if table is None:
        return {}

    result: dict[str, dict[int, float]] = {}

    # Parse header row for years
    year_cols: dict[int, int] = {}  # col_index -> year
    thead = table.find("thead")
    if thead:
        header_row = thead.find("tr")
        if header_row:
            for idx, th in enumerate(header_row.find_all(["th", "td"])):
                text = th.get_text(strip=True)
                m = re.search(r"(?:Mar|March|Sep|Sept|Jun|June|Dec)\s+(\d{2,4})", text, re.I)
                if m:
                    yr = int(m.group(1))
                    if yr < 100:
                        yr += 2000
                    year_cols[idx] = yr

    if not year_cols:
        return {}

    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue
        label = cells[0].get_text(strip=True).lower()
        label = re.sub(r"\s+", " ", label).strip()
        if not label:
            continue
        values: dict[int, float] = {}
        for col_idx, year in year_cols.items():
            if col_idx < len(cells):
                raw = cells[col_idx].get_text(strip=True).replace(",", "").replace("\xa0", "")
                # Handle negative in parentheses
                if raw.startswith("(") and raw.endswith(")"):
                    raw = "-" + raw[1:-1]
                try:
                    values[year] = float(raw)
                except ValueError:
                    pass
        if values:
            result[label] = values

    return result


def find_val(data: dict[str, dict[int, float]], patterns: list[str], year: int) -> float | None:
    for pat in patterns:
        pat_low = pat.lower()
        for label, vals in data.items():
            if pat_low in label or label in pat_low:
                if year in vals:
                    return vals[year]
    return None


# ── Build one CSV row ──────────────────────────────────────────────────────────

def build_row(company_name, cin, cohort, sector, year, pl, bs, cf) -> dict:
    revenue = find_val(pl, ["sales", "net sales", "revenue from operations", "total revenue"], year)
    pat = find_val(pl, ["net profit", "profit after tax", "pat"], year)
    interest = find_val(pl, ["interest", "finance cost", "finance costs"], year)
    depreciation = find_val(pl, ["depreciation", "depreciation and amortisation"], year)
    tax = find_val(pl, ["tax", "income tax", "provision for tax"], year)
    pbt = find_val(pl, ["profit before tax", "pbt", "profit/loss before tax"], year)

    ebitda = None
    if pbt is not None and interest is not None and depreciation is not None:
        ebitda = pbt + interest + depreciation

    # Screener shows equity_capital + reserves separately; sum them for total equity
    eq_capital = find_val(bs, ["equity capital"], year)
    reserves = find_val(bs, ["reserves"], year)
    if eq_capital is not None and reserves is not None:
        equity = eq_capital + reserves
    elif eq_capital is not None:
        equity = eq_capital
    else:
        equity = find_val(bs, ["net worth", "total equity", "shareholders funds"], year)

    # Screener shows combined borrowings (LT+ST) as 'borrowings'
    total_borrowings = find_val(bs, ["borrowings"], year)

    cur_assets = find_val(bs, ["current assets", "total current assets"], year)
    cur_liab = find_val(bs, ["current liabilities", "total current liabilities"], year)
    total_assets = find_val(bs, ["total assets", "total liabilities", "balance sheet total"], year)
    cash = find_val(bs, ["cash and cash equivalents", "cash & cash equivalents"], year)
    inventory = find_val(bs, ["inventories", "inventory"], year)
    receivables = find_val(bs, ["trade receivables", "sundry debtors", "debtors"], year)
    retained = find_val(bs, ["reserves"], year)  # Screener 'reserves' = reserves & surplus
    contingent = find_val(bs, ["contingent liabilities"], year)

    # Screener CF labels: "cash from operating activity+", etc.
    cfo = find_val(cf, ["cash from operating activity", "operating activities"], year)
    cfi = find_val(cf, ["cash from investing activity", "investing activities"], year)
    cff = find_val(cf, ["cash from financing activity", "financing activities"], year)
    net_cash = find_val(cf, ["net cash flow", "net change in cash", "net increase", "net decrease"], year)
    capex = find_val(cf, ["capital expenditure", "purchase of fixed assets", "fixed assets"], year)

    return {
        "company_name": company_name, "cin": cin, "financial_year": str(year),
        "cohort": cohort, "sector": sector,
        "revenue": fmt(revenue), "pat": fmt(pat),
        "interest_expense": fmt(interest), "depreciation": fmt(depreciation),
        "tax_expense": fmt(tax), "ebitda": fmt(ebitda),
        "total_equity": fmt(equity), "total_borrowings": fmt(total_borrowings),
        "current_assets": fmt(cur_assets), "current_liabilities": fmt(cur_liab),
        "total_assets": fmt(total_assets), "cash_and_equivalents": fmt(cash),
        "inventory": fmt(inventory), "receivables": fmt(receivables),
        "retained_earnings": fmt(retained),
        "cfo": fmt(cfo), "cfi": fmt(cfi), "cff": fmt(cff),
        "net_cash_change": fmt(net_cash), "capex": fmt(capex),
        "opinion_type": "", "going_concern_uncertainty": "", "emphasis_of_matter": "",
        "fraud_reported": "", "auditor_name": "",
        "related_party_transactions_amount": "",
        "contingent_liabilities_amount": fmt(contingent),
        "rpt_count": "", "pending_legal_cases_count": "", "promoter_holding_pct": "",
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ensure_csv(OUT_PATH, OUT_COLUMNS)
    ensure_csv(CHECKPOINT_PATH, ["cin", "financial_year"])
    ensure_csv(ERRORS_PATH,
        ["timestamp", "company_name", "cin", "financial_year", "cohort", "slug", "stage", "error"])

    checkpoint_done = load_checkpoint(CHECKPOINT_PATH)

    # Build company list from both CSVs
    companies: list[dict] = []
    for row in load_csv_rows(WILFUL_PATH):
        name = str(row.get("company_name", "")).strip()
        cin = str(row.get("cin", "")).strip()
        sector = str(row.get("sector", "")).strip()
        if name and cin:
            companies.append({"company_name": name, "cin": cin, "cohort": "defaulter", "sector": sector})

    for row in load_csv_rows(NON_DEFAULTER_PATH):
        name = str(row.get("company_name", "")).strip()
        cin = str(row.get("cin", "")).strip()
        sector = str(row.get("sector", "")).strip()
        if name and cin:
            companies.append({"company_name": name, "cin": cin, "cohort": "non_defaulter", "sector": sector})

    # Build years_by_cin from plan
    years_by_cin: dict[str, list[int]] = defaultdict(list)
    for row in load_csv_rows(PLAN_PATH):
        cin = str(row.get("cin", "")).strip()
        fy_raw = str(row.get("target_fy", "")).strip()
        if not cin or not fy_raw:
            continue
        try:
            fy = int(float(fy_raw))
            if fy not in years_by_cin[cin]:
                years_by_cin[cin].append(fy)
        except ValueError:
            pass
    for cin in years_by_cin:
        years_by_cin[cin] = sorted(set(years_by_cin[cin]), reverse=True)[:3]

    total = len(companies)
    session = requests.Session()

    for idx, company in enumerate(companies, start=1):
        company_name = company["company_name"]
        cin = company["cin"]
        cohort = company["cohort"]
        sector = company["sector"]

        plan_years = years_by_cin.get(cin, [])
        years_to_do = [y for y in plan_years if (cin, y) not in checkpoint_done]
        if not years_to_do:
            print(f"[{idx}/{total}] {company_name} — all years done, skipping")
            continue

        print(f"[{idx}/{total}] {company_name} (CIN: {cin}) years={years_to_do}")

        # Search Screener for slug
        slug = search_screener(session, company_name)
        if not slug:
            for year in years_to_do:
                log_error(company_name, cin, year, cohort, "", "search", "No Screener result")
            print(f"  NO RESULT on Screener")
            time.sleep(2.0)
            continue

        print(f"  Screener slug: {slug}")
        time.sleep(0.5)

        # Fetch company page
        soup = fetch_company_page(session, slug)
        if soup is None:
            for year in years_to_do:
                log_error(company_name, cin, year, cohort, slug, "fetch", "Failed to fetch page")
            print(f"  FETCH FAILED")
            time.sleep(2.0)
            continue

        # Parse tables
        try:
            pl = parse_screener_table(soup, "profit-loss")
            bs = parse_screener_table(soup, "balance-sheet")
            cf = parse_screener_table(soup, "cash-flow")
            print(f"  PL rows={len(pl)} BS rows={len(bs)} CF rows={len(cf)}")
        except Exception as exc:
            for year in years_to_do:
                log_error(company_name, cin, year, cohort, slug, "parse", str(exc))
            print(f"  PARSE ERROR: {exc}")
            time.sleep(2.0)
            continue

        for year in years_to_do:
            try:
                row = build_row(company_name, cin, cohort, sector, year, pl, bs, cf)
                append_row(OUT_PATH, OUT_COLUMNS, row)
                append_row(CHECKPOINT_PATH, ["cin", "financial_year"],
                           {"cin": cin, "financial_year": str(year)})
                checkpoint_done.add((cin, year))
                filled = sum(1 for k, v in row.items() if v and k not in ("company_name","cin","financial_year","cohort","sector"))
                print(f"  FY{year} OK — {filled} fields filled")
            except Exception as exc:
                log_error(company_name, cin, year, cohort, slug, "extract", str(exc))
                print(f"  FY{year} ERROR: {exc}")

        time.sleep(2.0)

    print(f"\nDone. Output: {OUT_PATH}")
    print(f"Errors: {ERRORS_PATH}")


if __name__ == "__main__":
    main()
