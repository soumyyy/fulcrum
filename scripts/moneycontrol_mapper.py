#!/usr/bin/env python3
from __future__ import annotations

import csv
import time
from pathlib import Path

import requests
from rapidfuzz import fuzz

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WILFUL_PATH = PROJECT_ROOT / "data" / "cibil" / "wilful_defaulters_50.csv"
NON_DEFAULTER_PATH = PROJECT_ROOT / "data" / "cibil" / "non_defaulters_50.csv"
OUT_PATH = PROJECT_ROOT / "data" / "processed" / "mc_code_mapping.csv"

AUTOSUGGEST_URL = "https://www.moneycontrol.com/mccode/common/autosuggestion/ajaxsearch.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.moneycontrol.com",
    "Accept": "text/plain, */*",
}
MATCH_THRESHOLD = 60
REQUEST_DELAY_SECONDS = 1.5


def normalize_name(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def parse_autosuggest_rows(raw_text: str) -> list[tuple[str, str]]:
    if not raw_text:
        return []
    candidates: list[tuple[str, str]] = []
    for line in raw_text.splitlines():
        row = line.strip()
        if not row or "|" not in row:
            continue
        parts = [p.strip() for p in row.split("|")]
        if len(parts) < 2:
            continue
        mc_code = parts[0]
        mc_name = parts[1]
        if mc_code and mc_name:
            candidates.append((mc_code, mc_name))
    return candidates


def pick_best_match(company_name: str, candidates: list[tuple[str, str]]) -> tuple[str, str, float]:
    best_code = ""
    best_name = ""
    best_score = 0.0
    normalized_company = normalize_name(company_name)

    for mc_code, mc_name in candidates:
        score = float(fuzz.token_sort_ratio(normalized_company, normalize_name(mc_name)))
        if score > best_score:
            best_score = score
            best_code = mc_code
            best_name = mc_name

    if best_score < MATCH_THRESHOLD:
        return "", "", best_score
    return best_code, best_name, best_score


def load_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_existing_cins(path: Path) -> set[str]:
    rows = load_csv_rows(path)
    return {str(r.get("cin", "")).strip() for r in rows if r.get("cin")}


def ensure_output_header(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["company_name", "cin", "cohort", "mc_code", "mc_name", "score"],
        )
        writer.writeheader()


def main() -> None:
    combined: list[dict] = []

    for row in load_csv_rows(WILFUL_PATH):
        name = str(row.get("company_name", "")).strip()
        cin = str(row.get("cin", "")).strip()
        if name and cin:
            combined.append({"company_name": name, "cin": cin, "cohort": "defaulter"})

    for row in load_csv_rows(NON_DEFAULTER_PATH):
        name = str(row.get("company_name", "")).strip()
        cin = str(row.get("cin", "")).strip()
        if name and cin:
            combined.append({"company_name": name, "cin": cin, "cohort": "non_defaulter"})

    ensure_output_header(OUT_PATH)
    done_cins = load_existing_cins(OUT_PATH)

    session = requests.Session()
    total = len(combined)

    with OUT_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["company_name", "cin", "cohort", "mc_code", "mc_name", "score"],
        )

        for idx, item in enumerate(combined, start=1):
            company_name = item["company_name"]
            cin = item["cin"]
            cohort = item["cohort"]

            if cin in done_cins:
                print(f"[{idx}/{total}] Skipping existing CIN: {cin}")
                continue

            mc_code = ""
            mc_name = ""
            score = ""
            try:
                response = session.get(
                    AUTOSUGGEST_URL,
                    params={
                        "classic": "true",
                        "query": company_name,
                        "type": "1",
                    },
                    headers=HEADERS,
                    timeout=20,
                )
                response.raise_for_status()
                candidates = parse_autosuggest_rows(response.text)
                mc_code, mc_name, best_score = pick_best_match(company_name, candidates)
                score = f"{best_score:.2f}" if best_score else ""
                if not mc_code:
                    print(f"[{idx}/{total}] NO_MATCH {company_name} (response: {repr(response.text[:100])})")
            except Exception as exc:
                print(f"[{idx}/{total}] ERROR {company_name} ({cin}): {exc}")

            writer.writerow(
                {
                    "company_name": company_name,
                    "cin": cin,
                    "cohort": cohort,
                    "mc_code": mc_code,
                    "mc_name": mc_name,
                    "score": score,
                }
            )
            f.flush()
            done_cins.add(cin)
            print(
                f"[{idx}/{total}] {company_name} ({cin}) -> "
                f"{mc_code or 'NO_MATCH'} score={score or ''}"
            )
            time.sleep(REQUEST_DELAY_SECONDS)

    print(f"Saved mapping to: {OUT_PATH}")


if __name__ == "__main__":
    main()
