#!/usr/bin/env python3
"""
Build model-ready ML features from the raw company-year dataset.

Input:
  data/processed/data.csv

Output:
  data/processed/model_features.csv

The script keeps the raw extracted columns and adds:
- target label
- core ratio features
- governance / audit flags
- company age from CIN
- year-over-year change features
- 3-year trend and volatility features

Usage:
  python scripts/build_model_features.py
  python scripts/build_model_features.py --input data/processed/data.csv --output data/processed/model_features.csv
"""
from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "data.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "model_features.csv"

RAW_NUMERIC_COLUMNS = [
    "financial_year",
    "revenue",
    "pat",
    "interest_expense",
    "depreciation",
    "tax_expense",
    "ebitda",
    "total_equity",
    "total_borrowings",
    "current_assets",
    "current_liabilities",
    "total_assets",
    "cash_and_equivalents",
    "inventory",
    "receivables",
    "retained_earnings",
    "cfo",
    "cfi",
    "cff",
    "net_cash_change",
    "capex",
    "going_concern_uncertainty",
    "emphasis_of_matter",
    "fraud_reported",
    "related_party_transactions_amount",
    "contingent_liabilities_amount",
    "rpt_count",
    "pending_legal_cases_count",
    "promoter_holding_pct",
]

TEMPORAL_BASE_COLUMNS = [
    "revenue",
    "pat",
    "ebitda",
    "total_borrowings",
    "cfo",
    "current_ratio",
    "debt_to_equity",
    "net_profit_margin",
    "roa",
    "promoter_holding_pct",
]

QUALIFIED_OPINIONS = {"qualified", "adverse", "disclaimer"}


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Elementwise divide, returning NaN if denominator is missing or zero."""
    denom = denominator.copy()
    invalid = denom.isna() | denom.eq(0)
    denom = denom.mask(invalid)
    return numerator / denom


def safe_positive_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Elementwise divide, returning NaN if denominator is missing, zero, or negative."""
    denom = denominator.copy()
    invalid = denom.isna() | denom.le(0)
    denom = denom.mask(invalid)
    return numerator / denom


def parse_incorporation_year(cin: str) -> float:
    """Extract incorporation year from CIN."""
    text = str(cin or "").strip().upper()
    match = re.match(r"^[A-Z]\d{5}[A-Z]{2}(\d{4})[A-Z]{3}\d{6}$", text)
    if not match:
        return math.nan
    year = int(match.group(1))
    if 1900 <= year <= 2100:
        return float(year)
    return math.nan


def normalized_text(series: pd.Series) -> pd.Series:
    """Normalize text columns so blank/null handling is consistent."""
    return series.fillna("").astype(str).str.strip()


def normalized_yoy_change(series: pd.Series) -> pd.Series:
    """
    YoY change normalized by absolute prior value.

    More stable than pct_change when the prior value is negative.
    """
    previous = series.shift(1)
    base = previous.abs()
    valid = previous.notna() & base.ne(0)
    out = pd.Series(math.nan, index=series.index, dtype="float64")
    out.loc[valid] = (series.loc[valid] - previous.loc[valid]) / base.loc[valid]
    return out


def difference_yoy(series: pd.Series) -> pd.Series:
    """Simple year-over-year difference."""
    return series - series.shift(1)


def slope_value(group: pd.DataFrame, column: str) -> float:
    """Return the linear slope across a company's available years for one column."""
    values = group[["financial_year", column]].dropna()
    if len(values) < 2:
        return math.nan
    x = values["financial_year"].astype(float)
    y = values[column].astype(float)
    x_mean = x.mean()
    y_mean = y.mean()
    denom = ((x - x_mean) ** 2).sum()
    if denom == 0:
        return math.nan
    return float((((x - x_mean) * (y - y_mean)).sum()) / denom)


def volatility_value(group: pd.DataFrame, column: str) -> float:
    """Return population standard deviation across a company's available years."""
    values = group[column].dropna().astype(float)
    if len(values) < 2:
        return math.nan
    return float(values.std(ddof=0))


def add_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add YoY, 3-year slope, and 3-year volatility features."""
    out = df.copy()
    out.sort_values(["company_name", "financial_year"], inplace=True)

    grouped = out.groupby("company_name", group_keys=False)

    for col in ["revenue", "pat", "ebitda", "total_borrowings", "cfo"]:
        out[f"{col}_yoy"] = grouped[col].transform(normalized_yoy_change)

    for col in ["current_ratio", "debt_to_equity", "net_profit_margin", "roa", "promoter_holding_pct"]:
        out[f"{col}_yoy"] = grouped[col].transform(difference_yoy)

    out["auditor_changed_yoy"] = grouped["auditor_name"].transform(
        lambda s: (
            normalized_text(s).ne(normalized_text(s).shift(1).fillna(""))
            & normalized_text(s).ne("")
            & normalized_text(s).shift(1).fillna("").ne("")
        ).astype(float)
    )

    out["latest_financial_year"] = grouped["financial_year"].transform("max")
    out["relative_year_from_latest"] = out["financial_year"] - out["latest_financial_year"]
    out["is_latest_observation"] = out["relative_year_from_latest"].eq(0).astype(int)

    company_groups = out.groupby("company_name").groups
    for col in TEMPORAL_BASE_COLUMNS:
        out[f"{col}_trend_3y"] = math.nan
        out[f"{col}_volatility_3y"] = math.nan
        for _, index in company_groups.items():
            group = out.loc[index, ["financial_year", col]]
            out.loc[index, f"{col}_trend_3y"] = slope_value(group, col)
            out.loc[index, f"{col}_volatility_3y"] = volatility_value(group, col)

    out["auditor_changed_3y"] = grouped["auditor_changed_yoy"].transform("max")
    out.drop(columns=["latest_financial_year"], inplace=True)
    return out


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    for col in RAW_NUMERIC_COLUMNS:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    out["target_wilful_default"] = out["cohort"].astype(str).str.strip().eq("defaulter").astype(int)
    out["incorporation_year"] = out["cin"].map(parse_incorporation_year)
    out["company_age"] = out["financial_year"] - out["incorporation_year"]

    out["ebit"] = out["pat"] + out["interest_expense"] + out["tax_expense"]
    out["working_capital"] = out["current_assets"] - out["current_liabilities"]
    out["total_liabilities_proxy"] = out["total_assets"] - out["total_equity"]

    out["capex_effective"] = out["capex"].abs()
    out["capex_effective"] = out["capex_effective"].fillna(out["cfi"].abs())
    out["free_cash_flow"] = out["cfo"] - out["capex_effective"]

    out["current_ratio"] = safe_divide(out["current_assets"], out["current_liabilities"])
    out["quick_ratio"] = safe_divide(out["current_assets"] - out["inventory"], out["current_liabilities"])
    out["cash_ratio"] = safe_divide(out["cash_and_equivalents"], out["current_liabilities"])

    out["debt_to_equity"] = safe_positive_divide(out["total_borrowings"], out["total_equity"])
    out["debt_to_assets"] = safe_divide(out["total_borrowings"], out["total_assets"])
    out["interest_coverage"] = safe_divide(out["ebit"], out["interest_expense"])
    out["debt_service_coverage_proxy"] = safe_divide(out["cfo"], out["interest_expense"])

    out["net_profit_margin"] = safe_divide(out["pat"], out["revenue"])
    out["ebitda_margin"] = safe_divide(out["ebitda"], out["revenue"])
    out["roa"] = safe_divide(out["pat"], out["total_assets"])
    out["roe"] = safe_positive_divide(out["pat"], out["total_equity"])

    out["asset_turnover"] = safe_divide(out["revenue"], out["total_assets"])
    out["receivables_turnover"] = safe_divide(out["revenue"], out["receivables"])
    out["cfo_margin"] = safe_divide(out["cfo"], out["revenue"])
    out["cash_flow_to_debt"] = safe_divide(out["cfo"], out["total_borrowings"])
    out["working_capital_to_assets"] = safe_divide(out["working_capital"], out["total_assets"])
    out["retained_earnings_to_assets"] = safe_divide(out["retained_earnings"], out["total_assets"])
    out["ebit_to_assets"] = safe_divide(out["ebit"], out["total_assets"])
    out["equity_ratio"] = safe_divide(out["total_equity"], out["total_assets"])
    out["current_liabilities_to_assets"] = safe_divide(out["current_liabilities"], out["total_assets"])

    out["rpt_to_revenue_ratio"] = safe_divide(out["related_party_transactions_amount"], out["revenue"])
    out["contingent_to_networth_ratio"] = safe_positive_divide(out["contingent_liabilities_amount"], out["total_equity"])

    out["auditor_qualification_flag"] = (
        normalized_text(out["opinion_type"])
        .str.lower()
        .isin(QUALIFIED_OPINIONS)
        .astype(int)
    )
    out["opinion_present_flag"] = normalized_text(out["opinion_type"]).ne("").astype(int)
    out["auditor_name_present_flag"] = normalized_text(out["auditor_name"]).ne("").astype(int)

    out["going_concern_uncertainty_flag"] = out["going_concern_uncertainty"].fillna(0).astype(int)
    out["emphasis_of_matter_flag"] = out["emphasis_of_matter"].fillna(0).astype(int)
    out["fraud_reported_flag"] = out["fraud_reported"].fillna(0).astype(int)
    out["related_party_flag"] = (
        out["related_party_transactions_amount"].fillna(0).gt(0)
        | out["rpt_count"].fillna(0).gt(0)
    ).astype(int)
    out["contingent_liability_flag"] = out["contingent_liabilities_amount"].fillna(0).gt(0).astype(int)

    for col in [
        "current_assets",
        "current_liabilities",
        "receivables",
        "capex",
        "opinion_type",
        "auditor_name",
        "contingent_liabilities_amount",
        "promoter_holding_pct",
    ]:
        feature_name = f"{col}_missing"
        if col in {"opinion_type", "auditor_name"}:
            out[feature_name] = normalized_text(out[col]).eq("").astype(int)
        else:
            out[feature_name] = out[col].isna().astype(int)

    out["altman_z_proxy"] = (
        1.2 * out["working_capital_to_assets"].fillna(0)
        + 1.4 * out["retained_earnings_to_assets"].fillna(0)
        + 3.3 * out["ebit_to_assets"].fillna(0)
        + 0.6 * safe_positive_divide(out["total_equity"], out["total_liabilities_proxy"]).fillna(0)
        + 1.0 * out["asset_turnover"].fillna(0)
    )

    out = add_temporal_features(out)

    out.sort_values(["company_name", "financial_year"], inplace=True)
    out.reset_index(drop=True, inplace=True)
    return out


def print_summary(df: pd.DataFrame) -> None:
    feature_cols = [
        c for c in df.columns
        if c not in {"company_name", "cin", "financial_year", "cohort", "sector", "opinion_type", "auditor_name"}
    ]
    print(f"Rows: {len(df)}")
    print(f"Companies: {df['company_name'].nunique()}")
    print(f"Columns: {len(df.columns)}")
    print(f"Derived feature columns: {len(feature_cols)}")
    print(f"Target balance: {df['target_wilful_default'].value_counts().to_dict()}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build ML-ready features from raw company-year data")
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Raw extracted dataset CSV")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output CSV with engineered features")
    args = ap.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input CSV not found: {args.input}")

    df = pd.read_csv(args.input)
    features = build_features(df)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(args.output, index=False)

    print(f"Wrote model features: {args.output}")
    print_summary(features)


if __name__ == "__main__":
    main()
