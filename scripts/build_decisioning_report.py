#!/usr/bin/env python3
"""
Build a markdown summary report from decisioning outputs.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LATEST = PROJECT_ROOT / "data" / "processed" / "decisioning_output_latest.csv"
DEFAULT_YEARS = PROJECT_ROOT / "data" / "processed" / "decisioning_output_years.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "DECISIONING_SUMMARY_REPORT.md"


def pct(value: float) -> str:
    return f"{value:.1%}"


def render_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    return df.fillna("").to_markdown(index=False)


def build_report(latest_df: pd.DataFrame, years_df: pd.DataFrame) -> str:
    total_companies = len(latest_df)
    total_years = len(years_df)
    urgent_count = int((latest_df["decision_bucket"] == "urgent_review").sum())
    disagree_count = int((latest_df["model_alignment"] == "disagree").sum())
    high_band_count = int((latest_df["engine_risk_band"] == "High").sum())

    bucket_summary = (
        latest_df.groupby("decision_bucket")
        .agg(
            companies=("cin", "size"),
            avg_engine_score=("engine_score_0_100", "mean"),
            avg_rule_flags=("rule_flag_count", "mean"),
            disagree_rate=("model_alignment", lambda s: (s == "disagree").mean()),
        )
        .reset_index()
        .sort_values(["companies", "avg_engine_score"], ascending=[False, False])
    )
    bucket_summary["avg_engine_score"] = bucket_summary["avg_engine_score"].round(2)
    bucket_summary["avg_rule_flags"] = bucket_summary["avg_rule_flags"].round(2)
    bucket_summary["disagree_rate"] = bucket_summary["disagree_rate"].map(pct)

    cohort_summary = (
        latest_df.groupby("cohort")
        .agg(
            companies=("cin", "size"),
            avg_engine_score=("engine_score_0_100", "mean"),
            high_band_rate=("engine_risk_band", lambda s: (s == "High").mean()),
            urgent_review_rate=("decision_bucket", lambda s: (s == "urgent_review").mean()),
        )
        .reset_index()
    )
    cohort_summary["avg_engine_score"] = cohort_summary["avg_engine_score"].round(2)
    cohort_summary["high_band_rate"] = cohort_summary["high_band_rate"].map(pct)
    cohort_summary["urgent_review_rate"] = cohort_summary["urgent_review_rate"].map(pct)

    top_urgent = latest_df.loc[latest_df["decision_bucket"] == "urgent_review", [
        "company_name",
        "financial_year",
        "sector",
        "engine_score_0_100",
        "audit_score_0_100",
        "rule_flag_count",
        "critical_rule_count",
        "top_reasons",
    ]].head(15).copy()

    disagreement_cases = latest_df.loc[latest_df["model_alignment"] == "disagree", [
        "company_name",
        "financial_year",
        "sector",
        "engine_score_0_100",
        "audit_score_0_100",
        "engine_risk_band",
        "audit_risk_band",
        "decision_bucket",
        "imputed_feature_fraction",
        "top_reasons",
    ]].copy()

    highest_confidence_monitor = latest_df.loc[latest_df["decision_bucket"] == "monitor", [
        "company_name",
        "financial_year",
        "sector",
        "engine_score_0_100",
        "audit_score_0_100",
        "rule_flag_count",
        "top_reasons",
    ]].tail(10).copy()

    sector_hotspots = (
        latest_df.groupby("sector")
        .agg(
            companies=("cin", "size"),
            avg_engine_score=("engine_score_0_100", "mean"),
            urgent_review_rate=("decision_bucket", lambda s: (s == "urgent_review").mean()),
        )
        .reset_index()
        .sort_values(["urgent_review_rate", "avg_engine_score"], ascending=[False, False])
        .head(12)
    )
    sector_hotspots["avg_engine_score"] = sector_hotspots["avg_engine_score"].round(2)
    sector_hotspots["urgent_review_rate"] = sector_hotspots["urgent_review_rate"].map(pct)

    report = f"""# Decisioning Summary Report

## Executive Summary

- Portfolio scored: **{total_companies} companies / {total_years} company-years**
- Production engine: **hist_gradient_boosting**
- Audit baseline: **logistic_regression**
- High-band latest rows: **{high_band_count} / {total_companies}**
- Urgent-review latest rows: **{urgent_count} / {total_companies}**
- Model disagreements on latest rows: **{disagree_count} / {total_companies}**

## What The Product Is

This is now a usable internal decisioning layer.

- The engine model ranks risk.
- The logistic model acts as a baseline audit check.
- Rule triggers provide support and narrative.
- The final action queue comes from `decision_bucket`, not from raw probability alone.

This is good enough for internal triage, screening, and portfolio review.
It is not yet a forward-looking default-timing model.

## Bucket Summary

{render_table(bucket_summary)}

## Cohort Summary

{render_table(cohort_summary)}

## Sector Hotspots

{render_table(sector_hotspots)}

## Top Urgent Review Names

{render_table(top_urgent)}

## Model Disagreement Cases

{render_table(disagreement_cases)}

## Lowest-Risk Monitor Names

{render_table(highest_confidence_monitor)}

## Reflection

The product is strongest where all three layers line up:

- engine probability is high
- logistic audit baseline agrees
- rule flags are present

That gives a credible internal action signal.

The current weakness is not feature engineering anymore. The weakness is product tuning:

- the urgent queue is still too broad
- sector-relative interpretation needs tighter use
- thresholding and bucket logic should be tuned against how you want analysts to work

## Recommended Next Moves

1. Reduce queue size by tightening `urgent_review` criteria.
2. Review the disagreement cases manually and decide whether disagreement should force `manual_check` more often.
3. Decide whether your operating unit works by:
   - bucket first, then score
   - or score first, then analyst override
4. Add a presentation layer next:
   - one portfolio dashboard
   - one company detail view
5. Only after that, revisit more data collection or label redesign.

## Operating Recommendation

Use these outputs in this order:

1. `/Users/soumya/Desktop/Projects/fulcrum/data/processed/decisioning_output_latest.csv`
2. `/Users/soumya/Desktop/Projects/fulcrum/data/processed/decisioning_output_years.csv`
3. this report for portfolio-level review

For actual workflow:

- `urgent_review`: immediate analyst review
- `review`: second queue
- `watchlist`: monitor
- `manual_check`: inspect disagreement / missingness
- `monitor`: no active action
"""
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="Build decisioning summary report")
    ap.add_argument("--latest", type=Path, default=DEFAULT_LATEST, help="Latest decisioning CSV")
    ap.add_argument("--years", type=Path, default=DEFAULT_YEARS, help="Yearwise decisioning CSV")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Markdown output path")
    args = ap.parse_args()

    if not args.latest.exists():
        raise FileNotFoundError(f"Latest output not found: {args.latest}")
    if not args.years.exists():
        raise FileNotFoundError(f"Year output not found: {args.years}")

    latest_df = pd.read_csv(args.latest)
    years_df = pd.read_csv(args.years)
    report = build_report(latest_df, years_df)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
