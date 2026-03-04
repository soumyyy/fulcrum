#!/usr/bin/env python3
"""
Shared scoring helpers for batch scoring and API inference.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

try:
    import yaml
except ImportError:  # pragma: no cover - runtime guard
    yaml = None

from build_model_features import build_features
from build_training_matrix import build_training_matrix_df
from risk_decision import evaluate_hybrid_decision, load_rules


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRAIN_CONFIG = PROJECT_ROOT / "config" / "model_train_config.yaml"
DEFAULT_RULES_CONFIG = PROJECT_ROOT / "config" / "risk_rules.yaml"
DEFAULT_PRODUCTION_ALIAS = PROJECT_ROOT / "artifacts" / "models" / "production_model.json"
MIN_REQUIRED_COLUMNS = [
    "company_name",
    "cin",
    "financial_year",
    "sector",
    "revenue",
    "pat",
    "interest_expense",
    "tax_expense",
    "total_equity",
    "total_borrowings",
    "total_assets",
    "cfo",
]
OPTIONAL_NUMERIC_COLUMNS = [
    "depreciation",
    "ebitda",
    "current_assets",
    "current_liabilities",
    "cash_and_equivalents",
    "inventory",
    "receivables",
    "retained_earnings",
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
SCHEMA_COLUMNS = MIN_REQUIRED_COLUMNS + OPTIONAL_NUMERIC_COLUMNS + ["cohort", "opinion_type", "auditor_name"]
HEURISTIC_REASON_LABELS = {
    "debt_to_equity": "Leverage is above the sector median.",
    "current_ratio": "Liquidity is weaker than the sector median.",
    "interest_coverage": "Interest coverage is weaker than the sector median.",
    "net_profit_margin": "Profitability is weaker than the sector median.",
    "cash_flow_to_debt": "Cash-flow-to-debt is weaker than the sector median.",
    "contingent_to_networth_ratio": "Contingent liabilities are elevated relative to sector peers.",
}


def load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise ImportError("PyYAML is required. Install with: pip install pyyaml")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML format in {path}")
    return data


def load_production_bundle(production_alias_path: Path = DEFAULT_PRODUCTION_ALIAS) -> tuple[dict[str, Any], dict[str, Any]]:
    if not production_alias_path.exists():
        raise FileNotFoundError(
            f"Production model manifest not found: {production_alias_path}. Run training first."
        )
    manifest = json.loads(production_alias_path.read_text(encoding="utf-8"))
    model_path = Path(manifest["model_path"])
    if not model_path.is_absolute():
        model_path = PROJECT_ROOT / model_path
    bundle = joblib.load(model_path)
    return bundle, manifest


def _ensure_schema_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in SCHEMA_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan
    return out


def validate_raw_input(df: pd.DataFrame, single_company: bool = False) -> pd.DataFrame:
    if df.empty:
        raise ValueError("Input CSV is empty")

    missing = [col for col in MIN_REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Input is missing required column(s): {missing}")

    out = _ensure_schema_columns(df)

    for col in ["company_name", "cin", "sector"]:
        if out[col].isna().any() or out[col].astype(str).str.strip().eq("").any():
            raise ValueError(f"Column '{col}' contains blank values")

    if single_company and out["cin"].astype(str).str.strip().nunique() != 1:
        raise ValueError("Single-company scoring accepts only one CIN per request")

    if out.duplicated(subset=["cin", "financial_year"]).any():
        raise ValueError("Duplicate (cin, financial_year) rows found in input")

    numeric_required = list(dict.fromkeys(MIN_REQUIRED_COLUMNS + OPTIONAL_NUMERIC_COLUMNS))
    numeric_required.remove("company_name")
    numeric_required.remove("cin")
    numeric_required.remove("sector")
    for col in numeric_required:
        if col not in out.columns:
            continue
        raw_text = out[col].fillna("").astype(str).str.strip()
        parsed = pd.to_numeric(raw_text.mask(raw_text.eq(""), other=np.nan), errors="coerce")
        invalid = raw_text.ne("") & parsed.isna()
        if invalid.any():
            raise ValueError(f"Column '{col}' contains non-numeric values")
        out[col] = parsed

    if out["financial_year"].isna().any():
        raise ValueError("Column 'financial_year' contains blank or invalid values")

    if out["ebitda"].isna().all():
        required_for_derivation = ["pat", "interest_expense", "tax_expense", "depreciation"]
        if any(out[col].isna().any() for col in required_for_derivation):
            raise ValueError(
                "Either 'ebitda' must be provided, or enough fields must exist to derive it "
                "(pat, interest_expense, tax_expense, depreciation)."
            )

    out["financial_year"] = out["financial_year"].astype(int)
    out["cohort"] = out["cohort"].fillna("unknown")
    out["opinion_type"] = out["opinion_type"].fillna("")
    out["auditor_name"] = out["auditor_name"].fillna("")
    return out


def _aligned_model_input(training_df: pd.DataFrame, bundle: dict[str, Any]) -> pd.DataFrame:
    expected_columns = list(bundle["input_columns"])
    aligned = training_df.copy()
    for col in expected_columns:
        if col not in aligned.columns:
            aligned[col] = np.nan
    return aligned.loc[:, expected_columns].copy()


def _logistic_model_reasons(bundle: dict[str, Any], model_input: pd.DataFrame, row_index: int) -> list[str]:
    pipeline = bundle["pipeline"]
    classifier = pipeline.named_steps["classifier"]
    if not hasattr(classifier, "coef_"):
        return []

    transformed = pipeline.named_steps["preprocessor"].transform(model_input.iloc[[row_index]])
    if hasattr(transformed, "toarray"):
        transformed = transformed.toarray()
    feature_names = bundle.get("transformed_feature_names", [])
    coefs = classifier.coef_[0]
    contributions = transformed[0] * coefs

    pairs = [
        (feature_names[idx], float(value))
        for idx, value in enumerate(contributions)
        if idx < len(feature_names) and value > 0
    ]
    pairs.sort(key=lambda item: item[1], reverse=True)
    reasons: list[str] = []
    for name, _ in pairs[:3]:
        cleaned = str(name).replace("num__", "").replace("cat__", "").replace("onehot__", "")
        cleaned = cleaned.replace("sector_", "sector=")
        reasons.append(f"Model-weighted risk contribution from {cleaned}.")
    return reasons


def _heuristic_model_reasons(feature_row: pd.Series, bundle: dict[str, Any]) -> list[str]:
    sector = str(feature_row.get("sector", ""))
    reference = bundle.get("sector_reference", {}).get(sector, {})
    reasons: list[str] = []

    for feature, label in HEURISTIC_REASON_LABELS.items():
        if feature not in feature_row or feature not in reference:
            continue
        value = pd.to_numeric(pd.Series([feature_row.get(feature)]), errors="coerce").iloc[0]
        median = reference.get(feature)
        if pd.isna(value) or median is None:
            continue
        if feature in {"debt_to_equity", "contingent_to_networth_ratio"} and value > median:
            reasons.append(label)
        elif feature in {"current_ratio", "interest_coverage", "net_profit_margin", "cash_flow_to_debt"} and value < median:
            reasons.append(label)
    return reasons[:3]


def _model_reasons(bundle: dict[str, Any], feature_row: pd.Series, model_input: pd.DataFrame, row_index: int) -> list[str]:
    reasons = _logistic_model_reasons(bundle, model_input, row_index)
    if reasons:
        return reasons
    return _heuristic_model_reasons(feature_row, bundle)


def _score_validated_company(
    validated: pd.DataFrame,
    train_config: dict[str, Any],
    rules_config: dict[str, Any],
    bundle: dict[str, Any],
) -> dict[str, Any]:
    feature_df = build_features(validated.copy())
    training_df = build_training_matrix_df(feature_df.copy(), train_config)
    model_input = _aligned_model_input(training_df, bundle)

    probabilities = bundle["pipeline"].predict_proba(model_input)[:, 1]
    threshold = float(bundle["threshold"])
    imputed_fraction = model_input.isna().sum(axis=1) / max(len(model_input.columns), 1)

    yearwise_scores: list[dict[str, Any]] = []
    for idx, (_, row) in enumerate(feature_df.iterrows()):
        model_reasons = _model_reasons(bundle, row, model_input, idx)
        decision = evaluate_hybrid_decision(
            row=row.to_dict(),
            ml_probability=float(probabilities[idx]),
            model_threshold=threshold,
            rules_config=rules_config,
            model_reasons=model_reasons,
        )
        yearwise_scores.append(
            {
                "financial_year": int(row["financial_year"]),
                **decision,
                "imputed_feature_fraction": float(imputed_fraction.iloc[idx]),
            }
        )

    latest_idx = feature_df["financial_year"].astype(int).idxmax()
    latest_year = int(feature_df.loc[latest_idx, "financial_year"])
    latest_score = next(item for item in yearwise_scores if item["financial_year"] == latest_year)

    warnings: list[str] = []
    if len(feature_df) == 1:
        warnings.append("Temporal trend features were unavailable; confidence is reduced.")
    if float(imputed_fraction.max()) > 0.30:
        warnings.append("More than 30% of model input features were imputed for at least one year.")
    if validated["sector"].astype(str).str.strip().iloc[0] not in set(bundle.get("sector_categories", [])):
        warnings.append("Sector is not represented in the training dataset; the score may be less reliable.")
    if latest_score["risk_band"] == "Medium" and latest_score["rule_flag_count"] == 0:
        warnings.append("The latest score is in the medium band without rule-based support; review manually.")

    key_missing_cols = ["revenue", "pat", "total_equity", "total_borrowings", "total_assets", "cfo"]
    if feature_df[key_missing_cols].isna().any(axis=None):
        warnings.append("One or more key financial fields were missing and had to be imputed.")

    return {
        "company_name": str(validated["company_name"].iloc[0]).strip(),
        "cin": str(validated["cin"].iloc[0]).strip(),
        "years_received": int(len(validated)),
        "latest_financial_year": latest_year,
        "model_name": str(bundle["model_name"]),
        "model_version": str(bundle.get("model_version", "v1")),
        "training_dataset_sha256": str(bundle.get("dataset_sha256", "")),
        "feature_list_version": str(bundle.get("feature_list_version", "")),
        "threshold_version": str(bundle.get("threshold_version", "")),
        "rule_set_version": str(rules_config.get("version", "")),
        "ml_probability": latest_score["ml_probability"],
        "model_threshold": latest_score["model_threshold"],
        "ml_class": latest_score["ml_class"],
        "risk_band": latest_score["risk_band"],
        "rule_flags_triggered": latest_score["rule_flags_triggered"],
        "rule_flag_count": latest_score["rule_flag_count"],
        "top_reasons": latest_score["top_reasons"],
        "support_summary": latest_score["support_summary"],
        "framing_message": latest_score["framing_message"],
        "yearwise_scores": yearwise_scores,
        "warnings": warnings,
    }


def score_single_company(
    raw_df: pd.DataFrame,
    train_config: dict[str, Any],
    rules_config: dict[str, Any],
    bundle: dict[str, Any],
) -> dict[str, Any]:
    validated = validate_raw_input(raw_df, single_company=True)
    return _score_validated_company(validated, train_config, rules_config, bundle)


def score_many_companies(
    raw_df: pd.DataFrame,
    train_config_path: Path = DEFAULT_TRAIN_CONFIG,
    rules_config_path: Path = DEFAULT_RULES_CONFIG,
    production_alias_path: Path = DEFAULT_PRODUCTION_ALIAS,
) -> list[dict[str, Any]]:
    train_config = load_yaml(train_config_path)
    rules_config = load_rules(rules_config_path)
    bundle, _manifest = load_production_bundle(production_alias_path)

    validated = validate_raw_input(raw_df, single_company=False)
    results: list[dict[str, Any]] = []
    for _, group in validated.groupby("cin", sort=False):
        results.append(_score_validated_company(group.copy(), train_config, rules_config, bundle))
    return results
