#!/usr/bin/env python3
"""
Build a financial-document download plan from cohort CSVs + config.

The output is one row per (company, financial_year, document_type) and includes:
- cohort
- anchor year logic result
- target financial years
- required/optional doc type
- source priority order

Usage:
  python scripts/build_financial_download_plan.py
  python scripts/build_financial_download_plan.py --config config/download_config.toml
"""
from __future__ import annotations

import argparse
import statistics
import tomllib
from pathlib import Path
from typing import Any, Optional

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "download_config.toml"
DEFAULT_DEFAULTERS = PROJECT_ROOT / "data" / "cibil" / "wilful_defaulters_50.csv"
DEFAULT_NON_DEFAULTERS = PROJECT_ROOT / "data" / "cibil" / "non_defaulters_50.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "financial_download_plan.csv"


def parse_year(value: Any) -> Optional[int]:
    """Parse year-like values such as 2021, '2021', '2021.0'."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "na", "none", "-"}:
        return None
    if text.endswith(".0"):
        text = text[:-2]
    try:
        year = int(text)
    except ValueError:
        return None
    if 1900 <= year <= 2100:
        return year
    return None


def ensure_columns(df: pd.DataFrame, required: list[str], label: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{label} missing required column(s): {missing}")


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("rb") as fh:
        return tomllib.load(fh)


def infer_defaulter_anchor(row: pd.Series, cfg: dict[str, Any], fallback_anchor: int) -> tuple[int, str]:
    mode = str(cfg.get("anchor_mode", "fy_before_default_or_default_minus_one")).strip().lower()

    if mode == "fixed_year":
        year = parse_year(cfg.get("fixed_anchor_fy"))
        if year:
            return year, "fixed_year"
        return fallback_anchor, "fallback_default_anchor_fy"

    if mode == "column":
        col = str(cfg.get("anchor_column", "anchor_fy"))
        year = parse_year(row.get(col))
        if year:
            return year, col
        return fallback_anchor, "fallback_default_anchor_fy"

    # Default mode: fy_before_default first, else default_year + offset.
    fy_col = str(cfg.get("fy_before_default_column", "fy_before_default"))
    default_col = str(cfg.get("default_year_column", "default_year"))
    offset = int(cfg.get("default_year_offset", -1))

    year = parse_year(row.get(fy_col))
    if year:
        return year, fy_col

    default_year = parse_year(row.get(default_col))
    if default_year:
        return default_year + offset, f"{default_col}{offset:+d}"

    return fallback_anchor, "fallback_default_anchor_fy"


def infer_non_defaulter_anchor(
    row: pd.Series,
    cfg: dict[str, Any],
    fallback_anchor: int,
    sector_medians: dict[str, int],
    global_median: int,
) -> tuple[int, str]:
    mode = str(cfg.get("anchor_mode", "sector_median_from_defaulters")).strip().lower()

    if mode == "fixed_year":
        year = parse_year(cfg.get("fixed_anchor_fy"))
        if year:
            return year, "fixed_year"
        return fallback_anchor, "fallback_default_anchor_fy"

    if mode == "column":
        col = str(cfg.get("anchor_column", "anchor_fy"))
        year = parse_year(row.get(col))
        if year:
            return year, col
        return fallback_anchor, "fallback_default_anchor_fy"

    if mode == "global_median_from_defaulters":
        return global_median, "global_median_from_defaulters"

    # Default: sector median from defaulters.
    raw_sector = str(row.get("sector", "")).strip()
    aliases = cfg.get("sector_aliases", {})
    sector = str(aliases.get(raw_sector, raw_sector)).strip()
    if sector and sector in sector_medians:
        return sector_medians[sector], "sector_median_from_defaulters"
    return global_median, "global_median_from_defaulters"


def years_from_anchor(anchor_fy: int, lookback_years: int, year_order: str) -> list[int]:
    years = [anchor_fy - i for i in range(lookback_years)]
    if year_order == "asc":
        years.reverse()
    return years


def cin_is_listed(cin: Any, listed_prefixes: list[str]) -> bool:
    text = str(cin or "").strip().upper()
    if not text:
        return False
    return any(text.startswith(prefix.upper()) for prefix in listed_prefixes)


def median_or_fallback(values: list[int], fallback: int) -> int:
    if not values:
        return fallback
    return int(round(statistics.median(values)))


def build_plan(
    defaulters: pd.DataFrame,
    non_defaulters: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    ensure_columns(defaulters, ["company_name", "cin", "sector"], "defaulters")
    ensure_columns(non_defaulters, ["company_name", "cin", "sector"], "non_defaulters")

    general = config.get("general", {})
    def_cfg = config.get("defaulters", {})
    non_cfg = config.get("non_defaulters", {})
    src_cfg = config.get("sources", {})
    doc_cfg = config.get("documents", {})

    lookback_years = int(general.get("lookback_years", 3))
    default_anchor = int(general.get("default_anchor_fy", 2023))
    year_order = str(general.get("year_order", "desc")).strip().lower()
    if year_order not in {"asc", "desc"}:
        raise ValueError("general.year_order must be 'asc' or 'desc'")

    listed_prefixes = [str(v) for v in src_cfg.get("listed_cin_prefixes", ["L"])]
    priority_listed = [str(v) for v in src_cfg.get("priority_listed", ["bse", "nse", "mca"])]
    priority_unlisted = [str(v) for v in src_cfg.get("priority_unlisted", ["mca"])]

    required_docs = [str(v) for v in doc_cfg.get("required", [])]
    optional_docs = [str(v) for v in doc_cfg.get("optional", [])]
    if not required_docs:
        raise ValueError("documents.required cannot be empty")

    # Compute defaulter anchor years first (needed for non-defaulter matching modes).
    def_with_anchor = defaulters.copy()
    def_with_anchor["anchor_fy"] = None
    def_with_anchor["anchor_reason"] = ""

    for idx, row in def_with_anchor.iterrows():
        anchor, reason = infer_defaulter_anchor(row, def_cfg, default_anchor)
        def_with_anchor.at[idx, "anchor_fy"] = anchor
        def_with_anchor.at[idx, "anchor_reason"] = reason

    valid_anchors = [int(v) for v in def_with_anchor["anchor_fy"].dropna().tolist()]
    global_median = median_or_fallback(valid_anchors, default_anchor)

    sector_medians: dict[str, int] = {}
    for sector, grp in def_with_anchor.groupby("sector", dropna=False):
        vals = [int(v) for v in grp["anchor_fy"].dropna().tolist()]
        sector_key = str(sector).strip()
        if not sector_key:
            continue
        sector_medians[sector_key] = median_or_fallback(vals, global_median)

    plan_rows: list[dict[str, Any]] = []

    def append_company_rows(row: pd.Series, cohort: str, anchor_fy: int, anchor_reason: str) -> None:
        is_listed = cin_is_listed(row.get("cin"), listed_prefixes)
        source_priority = priority_listed if is_listed else priority_unlisted
        years = years_from_anchor(anchor_fy, lookback_years, year_order)
        source_priority_text = "|".join(source_priority)

        base = {
            "cohort": cohort,
            "company_name": str(row.get("company_name", "")).strip(),
            "cin": str(row.get("cin", "")).strip().upper(),
            "sector": str(row.get("sector", "")).strip(),
            "is_listed": is_listed,
            "anchor_fy": anchor_fy,
            "anchor_reason": anchor_reason,
            "source_priority": source_priority_text,
            "default_year": parse_year(row.get("default_year")),
            "fy_before_default": parse_year(row.get("fy_before_default")),
        }

        for year in years:
            for doc in required_docs:
                r = base.copy()
                r["target_fy"] = year
                r["doc_type"] = doc
                r["required"] = True
                plan_rows.append(r)
            for doc in optional_docs:
                r = base.copy()
                r["target_fy"] = year
                r["doc_type"] = doc
                r["required"] = False
                plan_rows.append(r)

    for _, row in def_with_anchor.iterrows():
        append_company_rows(row, "defaulter", int(row["anchor_fy"]), str(row["anchor_reason"]))

    for _, row in non_defaulters.iterrows():
        anchor, reason = infer_non_defaulter_anchor(row, non_cfg, default_anchor, sector_medians, global_median)
        append_company_rows(row, "non_defaulter", anchor, reason)

    plan = pd.DataFrame(plan_rows)
    plan.sort_values(
        by=["cohort", "company_name", "target_fy", "required", "doc_type"],
        ascending=[True, True, False, False, True],
        inplace=True,
    )
    plan.reset_index(drop=True, inplace=True)
    return plan


def print_summary(plan: pd.DataFrame) -> None:
    companies = plan[["cohort", "company_name"]].drop_duplicates()
    years = plan[["company_name", "target_fy"]].drop_duplicates()
    required_docs = plan[plan["required"]]
    optional_docs = plan[~plan["required"]]

    print(f"Companies in plan: {len(companies)}")
    print(f"Company-year targets: {len(years)}")
    print(f"Required jobs: {len(required_docs)}")
    print(f"Optional jobs: {len(optional_docs)}")
    print(f"Total jobs: {len(plan)}")

    cohort_counts = companies.groupby("cohort").size().to_dict()
    print(f"Cohort company counts: {cohort_counts}")

    source_counts = (
        plan[["company_name", "source_priority"]]
        .drop_duplicates()
        .groupby("source_priority")
        .size()
        .sort_values(ascending=False)
        .to_dict()
    )
    print(f"Source priority profiles: {source_counts}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build financial-data download plan for all companies")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="TOML config file")
    ap.add_argument("--defaulters", type=Path, default=DEFAULT_DEFAULTERS, help="Defaulter cohort CSV")
    ap.add_argument("--non-defaulters", type=Path, default=DEFAULT_NON_DEFAULTERS, help="Non-defaulter cohort CSV")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output CSV path")
    args = ap.parse_args()

    cfg = load_config(args.config)
    defaulters = pd.read_csv(args.defaulters, dtype=str).fillna("")
    non_defaulters = pd.read_csv(args.non_defaulters, dtype=str).fillna("")

    plan = build_plan(defaulters, non_defaulters, cfg)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    plan.to_csv(args.output, index=False)

    print(f"Wrote plan: {args.output}")
    print_summary(plan)


if __name__ == "__main__":
    main()
