#!/usr/bin/env python3
"""
Build final decisioning outputs from the Tier 1A model stack.

Outputs:
- data/processed/decisioning_output_years.csv
- data/processed/decisioning_output_latest.csv
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from build_model_features import build_features
from build_training_matrix import build_training_matrix_df, load_config
from risk_decision import evaluate_hybrid_decision, load_rules
from scoring_utils import _model_reasons, load_production_bundle, validate_raw_input
from train_models import apply_probability_calibrator


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "data.csv"
DEFAULT_TRAIN_CONFIG = PROJECT_ROOT / "config" / "model_train_config_tier1a.yaml"
DEFAULT_RULES_CONFIG = PROJECT_ROOT / "config" / "risk_rules.yaml"
DEFAULT_ENGINE_MANIFEST = PROJECT_ROOT / "artifacts" / "models" / "production_model.json"
DEFAULT_AUDIT_MODEL = PROJECT_ROOT / "artifacts" / "models" / "logistic_regression.joblib"
DEFAULT_YEARS_OUTPUT = PROJECT_ROOT / "data" / "processed" / "decisioning_output_years.csv"
DEFAULT_LATEST_OUTPUT = PROJECT_ROOT / "data" / "processed" / "decisioning_output_latest.csv"


def align_model_input(training_df: pd.DataFrame, bundle: dict[str, Any]) -> pd.DataFrame:
    expected_columns = list(bundle["input_columns"])
    aligned = training_df.copy()
    for col in expected_columns:
        if col not in aligned.columns:
            aligned[col] = np.nan
    return aligned.loc[:, expected_columns].copy()


def probability_band(probability: float, threshold: float) -> str:
    if probability >= threshold:
        return "High"
    if probability >= (threshold - 0.15):
        return "Medium"
    return "Low"


def decision_bucket(
    engine_band: str,
    engine_class: int,
    audit_class: int,
    rule_flag_count: int,
    critical_rule_count: int,
    imputed_feature_fraction: float,
    engine_audit_gap: float,
) -> str:
    if engine_class == 1 and audit_class == 1 and (critical_rule_count >= 1 or rule_flag_count >= 4):
        return "urgent_review"
    if engine_class != audit_class or imputed_feature_fraction > 0.20:
        return "manual_check"
    if (
        (engine_class == 1 and audit_class == 1)
        or (engine_class == 1 and rule_flag_count >= 2)
        or (audit_class == 1 and critical_rule_count >= 1)
    ):
        return "review"
    if engine_class == 1 or audit_class == 1 or rule_flag_count >= 2 or engine_audit_gap >= 0.15:
        return "watchlist"
    return "monitor"


def bucket_priority(bucket: str) -> int:
    order = {
        "urgent_review": 1,
        "review": 2,
        "manual_check": 3,
        "watchlist": 4,
        "monitor": 5,
    }
    return order.get(bucket, 99)


def percentile(series: pd.Series) -> pd.Series:
    return (series.rank(method="average", pct=True) * 100).round(2)


def build_outputs(
    raw_df: pd.DataFrame,
    train_config: dict[str, Any],
    rules_config: dict[str, Any],
    engine_bundle: dict[str, Any],
    audit_bundle: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    validated = validate_raw_input(raw_df, single_company=False)
    feature_df = build_features(validated.copy())
    training_df = build_training_matrix_df(feature_df.copy(), train_config)

    engine_input = align_model_input(training_df, engine_bundle)
    audit_input = align_model_input(training_df, audit_bundle)

    engine_raw_probs = engine_bundle["pipeline"].predict_proba(engine_input)[:, 1]
    engine_probs = apply_probability_calibrator(engine_bundle.get("calibrator"), engine_raw_probs)
    audit_raw_probs = audit_bundle["pipeline"].predict_proba(audit_input)[:, 1]
    audit_probs = apply_probability_calibrator(audit_bundle.get("calibrator"), audit_raw_probs)

    engine_threshold = float(engine_bundle["threshold"])
    audit_threshold = float(audit_bundle["threshold"])
    imputed_fraction = engine_input.isna().sum(axis=1) / max(len(engine_input.columns), 1)

    rows: list[dict[str, Any]] = []
    for idx, (_, row) in enumerate(feature_df.iterrows()):
        model_reasons = _model_reasons(engine_bundle, row, engine_input, idx)
        engine_decision = evaluate_hybrid_decision(
            row=row.to_dict(),
            ml_probability=float(engine_probs[idx]),
            model_threshold=engine_threshold,
            rules_config=rules_config,
            model_reasons=model_reasons,
        )
        audit_prob = float(audit_probs[idx])
        audit_class = int(audit_prob >= audit_threshold)
        audit_band = probability_band(audit_prob, audit_threshold)
        engine_audit_gap = abs(float(engine_decision["ml_probability"]) - audit_prob)
        model_alignment = "agree" if int(engine_decision["ml_class"]) == audit_class else "disagree"
        bucket = decision_bucket(
            engine_band=str(engine_decision["risk_band"]),
            engine_class=int(engine_decision["ml_class"]),
            audit_class=audit_class,
            rule_flag_count=int(engine_decision["rule_flag_count"]),
            critical_rule_count=int(engine_decision["critical_rule_count"]),
            imputed_feature_fraction=float(imputed_fraction.iloc[idx]),
            engine_audit_gap=float(engine_audit_gap),
        )

        rows.append(
            {
                "company_name": str(row["company_name"]).strip(),
                "cin": str(row["cin"]).strip(),
                "sector": str(row.get("sector", "")).strip(),
                "cohort": str(row.get("cohort", "")).strip(),
                "financial_year": int(row["financial_year"]),
                "engine_model_name": str(engine_bundle["model_name"]),
                "engine_model_version": str(engine_bundle.get("model_version", "")),
                "engine_probability": float(engine_decision["ml_probability"]),
                "engine_score_0_100": round(float(engine_decision["ml_probability"]) * 100, 2),
                "engine_threshold": engine_threshold,
                "engine_class": int(engine_decision["ml_class"]),
                "engine_risk_band": str(engine_decision["risk_band"]),
                "audit_model_name": str(audit_bundle["model_name"]),
                "audit_model_version": str(audit_bundle.get("model_version", "")),
                "audit_probability": audit_prob,
                "audit_score_0_100": round(audit_prob * 100, 2),
                "audit_threshold": audit_threshold,
                "audit_class": audit_class,
                "audit_risk_band": audit_band,
                "engine_audit_gap": float(engine_audit_gap),
                "model_alignment": model_alignment,
                "rule_flag_count": int(engine_decision["rule_flag_count"]),
                "critical_rule_count": int(engine_decision["critical_rule_count"]),
                "rule_flags_triggered": "|".join(engine_decision["rule_flags_triggered"]),
                "top_reasons": " | ".join(engine_decision["top_reasons"]),
                "support_summary": str(engine_decision["support_summary"]),
                "imputed_feature_fraction": float(imputed_fraction.iloc[idx]),
                "decision_bucket": bucket,
                "decision_priority": bucket_priority(bucket),
            }
        )

    years_df = pd.DataFrame(rows)
    years_df["overall_risk_percentile"] = percentile(years_df["engine_probability"])
    years_df["sector_risk_percentile"] = (
        years_df.groupby("sector")["engine_probability"].transform(percentile)
    )
    years_df["sector_year_risk_percentile"] = (
        years_df.groupby(["sector", "financial_year"])["engine_probability"].transform(percentile)
    )
    years_df["engine_rank_overall"] = years_df["engine_probability"].rank(method="first", ascending=False).astype(int)
    years_df.sort_values(
        by=["decision_priority", "engine_probability", "rule_flag_count", "company_name", "financial_year"],
        ascending=[True, False, False, True, True],
        inplace=True,
    )

    latest_idx = years_df.groupby("cin")["financial_year"].idxmax()
    latest_df = years_df.loc[latest_idx].copy()
    latest_df["latest_overall_risk_percentile"] = percentile(latest_df["engine_probability"])
    latest_df["latest_sector_risk_percentile"] = (
        latest_df.groupby("sector")["engine_probability"].transform(percentile)
    )
    latest_df["latest_engine_rank"] = latest_df["engine_probability"].rank(method="first", ascending=False).astype(int)
    latest_df.sort_values(
        by=["decision_priority", "engine_probability", "rule_flag_count", "company_name"],
        ascending=[True, False, False, True],
        inplace=True,
    )

    preferred_year_columns = [
        "company_name",
        "cin",
        "sector",
        "cohort",
        "financial_year",
        "engine_probability",
        "engine_score_0_100",
        "engine_risk_band",
        "audit_probability",
        "audit_score_0_100",
        "audit_risk_band",
        "engine_audit_gap",
        "model_alignment",
        "rule_flag_count",
        "critical_rule_count",
        "decision_bucket",
        "overall_risk_percentile",
        "sector_risk_percentile",
        "sector_year_risk_percentile",
        "imputed_feature_fraction",
        "top_reasons",
        "rule_flags_triggered",
        "support_summary",
        "engine_model_name",
        "audit_model_name",
        "engine_model_version",
        "audit_model_version",
        "engine_threshold",
        "audit_threshold",
        "engine_class",
        "audit_class",
        "engine_rank_overall",
    ]
    preferred_latest_columns = [
        "company_name",
        "cin",
        "sector",
        "cohort",
        "financial_year",
        "engine_probability",
        "engine_score_0_100",
        "engine_risk_band",
        "audit_probability",
        "audit_score_0_100",
        "audit_risk_band",
        "engine_audit_gap",
        "model_alignment",
        "rule_flag_count",
        "critical_rule_count",
        "decision_bucket",
        "latest_overall_risk_percentile",
        "latest_sector_risk_percentile",
        "latest_engine_rank",
        "imputed_feature_fraction",
        "top_reasons",
        "rule_flags_triggered",
        "support_summary",
        "engine_model_name",
        "audit_model_name",
        "engine_model_version",
        "audit_model_version",
        "engine_threshold",
        "audit_threshold",
        "engine_class",
        "audit_class",
    ]
    years_df = years_df.loc[:, preferred_year_columns]
    latest_df = latest_df.loc[:, preferred_latest_columns]
    return years_df, latest_df


def main() -> None:
    ap = argparse.ArgumentParser(description="Build decisioning outputs from trained models")
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Raw company-year input CSV")
    ap.add_argument("--train-config", type=Path, default=DEFAULT_TRAIN_CONFIG, help="Training config YAML")
    ap.add_argument("--rules-config", type=Path, default=DEFAULT_RULES_CONFIG, help="Risk rules YAML")
    ap.add_argument("--engine-manifest", type=Path, default=DEFAULT_ENGINE_MANIFEST, help="Production model manifest JSON")
    ap.add_argument("--audit-model", type=Path, default=DEFAULT_AUDIT_MODEL, help="Audit baseline joblib bundle")
    ap.add_argument("--year-output", type=Path, default=DEFAULT_YEARS_OUTPUT, help="Full company-year output CSV")
    ap.add_argument("--latest-output", type=Path, default=DEFAULT_LATEST_OUTPUT, help="Latest company output CSV")
    args = ap.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input CSV not found: {args.input}")
    if not args.train_config.exists():
        raise FileNotFoundError(f"Training config not found: {args.train_config}")
    if not args.rules_config.exists():
        raise FileNotFoundError(f"Rules config not found: {args.rules_config}")
    if not args.audit_model.exists():
        raise FileNotFoundError(f"Audit baseline bundle not found: {args.audit_model}")

    train_config = load_config(args.train_config)
    rules_config = load_rules(args.rules_config)
    engine_bundle, _engine_manifest = load_production_bundle(args.engine_manifest)
    audit_bundle = joblib.load(args.audit_model)
    raw_df = pd.read_csv(args.input)

    years_df, latest_df = build_outputs(raw_df, train_config, rules_config, engine_bundle, audit_bundle)

    args.year_output.parent.mkdir(parents=True, exist_ok=True)
    args.latest_output.parent.mkdir(parents=True, exist_ok=True)
    years_df.to_csv(args.year_output, index=False)
    latest_df.to_csv(args.latest_output, index=False)

    summary = {
        "engine_model": str(engine_bundle["model_name"]),
        "audit_model": str(audit_bundle["model_name"]),
        "years_rows": int(len(years_df)),
        "latest_rows": int(len(latest_df)),
        "decision_bucket_counts_latest": latest_df["decision_bucket"].value_counts().to_dict(),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
