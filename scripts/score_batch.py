#!/usr/bin/env python3
"""
Batch score one or more companies from a raw-input CSV.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from scoring_utils import (
    DEFAULT_PRODUCTION_ALIAS,
    DEFAULT_RULES_CONFIG,
    DEFAULT_TRAIN_CONFIG,
    score_many_companies,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "data.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "scored_companies.csv"


def flatten_results(results: list[dict]) -> pd.DataFrame:
    rows: list[dict] = []
    for item in results:
        rows.append(
            {
                "company_name": item["company_name"],
                "cin": item["cin"],
                "years_received": item["years_received"],
                "latest_financial_year": item["latest_financial_year"],
                "model_name": item["model_name"],
                "model_version": item["model_version"],
                "ml_probability": item["ml_probability"],
                "model_threshold": item["model_threshold"],
                "ml_class": item["ml_class"],
                "risk_band": item["risk_band"],
                "rule_flags_triggered": "|".join(item["rule_flags_triggered"]),
                "rule_flag_count": item["rule_flag_count"],
                "top_reasons": " | ".join(item["top_reasons"]),
                "support_summary": item["support_summary"],
                "warnings": " | ".join(item["warnings"]),
                "yearwise_scores_json": json.dumps(item["yearwise_scores"]),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description="Batch score companies from a raw-input CSV")
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Raw-input CSV")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Scored output CSV")
    ap.add_argument("--train-config", type=Path, default=DEFAULT_TRAIN_CONFIG, help="Training config YAML")
    ap.add_argument("--rules-config", type=Path, default=DEFAULT_RULES_CONFIG, help="Risk rules YAML")
    ap.add_argument("--production-manifest", type=Path, default=DEFAULT_PRODUCTION_ALIAS, help="Production model manifest")
    args = ap.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input CSV not found: {args.input}")

    raw_df = pd.read_csv(args.input)
    results = score_many_companies(
        raw_df,
        train_config_path=args.train_config,
        rules_config_path=args.rules_config,
        production_alias_path=args.production_manifest,
    )
    out_df = flatten_results(results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(args.output, index=False)

    print(f"Wrote scored companies: {args.output}")
    print(f"Companies scored: {len(out_df)}")


if __name__ == "__main__":
    main()
