#!/usr/bin/env python3
"""
Train and compare V1 Fulcrum models using a company-grouped split.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

try:
    import yaml
except ImportError:  # pragma: no cover - runtime guard
    yaml = None

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "training_matrix.csv"
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "model_train_config.yaml"
REFERENCE_FEATURES = [
    "debt_to_equity",
    "current_ratio",
    "interest_coverage",
    "net_profit_margin",
    "cash_flow_to_debt",
    "contingent_to_networth_ratio",
]
MODEL_PRIORITY = {
    "logistic_regression": 0,
    "random_forest": 1,
    "hist_gradient_boosting": 2,
}


@dataclass
class TrainedModelResult:
    model_name: str
    bundle: dict[str, Any]
    validation_metrics: dict[str, Any]
    test_metrics: dict[str, Any]
    params: dict[str, Any]


def load_config(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise ImportError("PyYAML is required. Install with: pip install pyyaml")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid config format in {path}")
    return data


def sha256_for_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def make_one_hot_encoder(categories: list[str]) -> OneHotEncoder:
    try:
        return OneHotEncoder(categories=[categories], handle_unknown="ignore", sparse_output=False)
    except TypeError:  # pragma: no cover - older sklearn
        return OneHotEncoder(categories=[categories], handle_unknown="ignore", sparse=False)


def ensure_numeric(df: pd.DataFrame, columns: list[str]) -> None:
    for col in columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")


def validate_dataset(df: pd.DataFrame, config: dict[str, Any]) -> None:
    dataset_cfg = config.get("dataset", {})
    id_columns = list(dataset_cfg.get("id_columns", []))
    label_column = str(dataset_cfg.get("label_column", "target_wilful_default"))
    required = id_columns + [label_column]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Training matrix missing required columns: {missing}")

    if df[label_column].nunique() < 2:
        raise ValueError("Training matrix must contain at least two label classes")

    dupes = df.duplicated(subset=["cin", "financial_year"])
    if dupes.any():
        raise ValueError("Duplicate (cin, financial_year) rows found in training matrix")

    company_labels = df.groupby("cin")[label_column].nunique()
    if (company_labels > 1).any():
        raise ValueError("A company maps to multiple labels; company-level split would be invalid")


def split_by_company(df: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    label_column = str(config.get("dataset", {}).get("label_column", "target_wilful_default"))
    split_cfg = config.get("splits", {})
    train_companies = int(split_cfg.get("train_companies", 70))
    val_companies = int(split_cfg.get("validation_companies", 15))
    test_companies = int(split_cfg.get("test_companies", 15))
    seed = int(split_cfg.get("random_seed", 42))

    company_df = (
        df[["cin", "company_name", label_column]]
        .drop_duplicates(subset=["cin"])
        .reset_index(drop=True)
    )

    total_companies = len(company_df)
    if train_companies + val_companies + test_companies != total_companies:
        raise ValueError(
            f"Company split counts must sum to {total_companies}, got "
            f"{train_companies + val_companies + test_companies}"
        )

    train_comp, temp_comp = train_test_split(
        company_df,
        train_size=train_companies,
        stratify=company_df[label_column],
        random_state=seed,
    )

    val_fraction = val_companies / (val_companies + test_companies)
    val_comp, test_comp = train_test_split(
        temp_comp,
        train_size=val_fraction,
        stratify=temp_comp[label_column],
        random_state=seed,
    )

    train_df = df[df["cin"].isin(train_comp["cin"])].copy()
    val_df = df[df["cin"].isin(val_comp["cin"])].copy()
    test_df = df[df["cin"].isin(test_comp["cin"])].copy()

    for name, split_df in {"train": train_df, "validation": val_df, "test": test_df}.items():
        if split_df[label_column].nunique() < 2:
            raise ValueError(f"{name} split contains only one class")
    return train_df, val_df, test_df


def select_numeric_features(train_df: pd.DataFrame, full_df: pd.DataFrame, config: dict[str, Any]) -> list[str]:
    dataset_cfg = config.get("dataset", {})
    id_columns = set(dataset_cfg.get("id_columns", []))
    label_column = str(dataset_cfg.get("label_column", "target_wilful_default"))
    categorical_columns = set(dataset_cfg.get("categorical_columns", []))

    candidate_cols = [
        col for col in full_df.columns
        if col not in id_columns and col != label_column and col not in categorical_columns
    ]
    ensure_numeric(train_df, candidate_cols)
    ensure_numeric(full_df, candidate_cols)

    non_constant = [
        col for col in candidate_cols
        if train_df[col].nunique(dropna=False) > 1
    ]
    if not non_constant:
        raise ValueError("No usable numeric features remain after zero-variance filtering")

    corr_threshold = float(config.get("preprocessing", {}).get("correlation_threshold", 0.90))
    corr_frame = train_df[non_constant].corr().abs()
    upper = corr_frame.where(np.triu(np.ones(corr_frame.shape), k=1).astype(bool))
    drop_cols = {column for column in upper.columns if (upper[column] > corr_threshold).any()}

    selected = [col for col in non_constant if col not in drop_cols]
    if not selected:
        raise ValueError("Correlation filtering removed all numeric features")
    return selected


def build_preprocessor(
    numeric_columns: list[str],
    categorical_columns: list[str],
    sector_categories: list[str],
    scale_numeric: bool,
) -> ColumnTransformer:
    numeric_steps: list[tuple[str, Any]] = [("imputer", SimpleImputer(strategy="median"))]
    if scale_numeric:
        numeric_steps.append(("scaler", StandardScaler()))

    transformers = [
        ("num", Pipeline(numeric_steps), numeric_columns),
        (
            "cat",
            Pipeline(
                [
                    ("imputer", SimpleImputer(strategy="most_frequent")),
                    ("onehot", make_one_hot_encoder(sector_categories)),
                ]
            ),
            categorical_columns,
        ),
    ]
    return ColumnTransformer(transformers=transformers, remainder="drop")


def build_model_candidates(config: dict[str, Any]) -> dict[str, list[tuple[dict[str, Any], Any, bool]]]:
    model_cfg = config.get("models", {})
    candidates: dict[str, list[tuple[dict[str, Any], Any, bool]]] = {}

    log_cfg = model_cfg.get("logistic_regression", {})
    if log_cfg.get("enabled", True):
        candidates["logistic_regression"] = []
        for c_value in log_cfg.get("C_grid", [1.0]):
            params = {"C": float(c_value)}
            estimator = LogisticRegression(
                C=float(c_value),
                class_weight="balanced",
                penalty="l2",
                solver="liblinear",
                max_iter=2000,
                random_state=42,
            )
            candidates["logistic_regression"].append((params, estimator, True))

    rf_cfg = model_cfg.get("random_forest", {})
    if rf_cfg.get("enabled", True):
        candidates["random_forest"] = []
        for n_estimators, max_depth, min_leaf, max_features in product(
            rf_cfg.get("n_estimators", [200]),
            rf_cfg.get("max_depth", [15]),
            rf_cfg.get("min_samples_leaf", [1]),
            rf_cfg.get("max_features", ["sqrt"]),
        ):
            params = {
                "n_estimators": int(n_estimators),
                "max_depth": int(max_depth),
                "min_samples_leaf": int(min_leaf),
                "max_features": max_features,
            }
            estimator = RandomForestClassifier(
                n_estimators=int(n_estimators),
                max_depth=int(max_depth),
                min_samples_leaf=int(min_leaf),
                max_features=max_features,
                class_weight="balanced",
                random_state=42,
                n_jobs=1,
            )
            candidates["random_forest"].append((params, estimator, False))

    hgb_cfg = model_cfg.get("hist_gradient_boosting", {})
    if hgb_cfg.get("enabled", True):
        candidates["hist_gradient_boosting"] = []
        for learning_rate, max_depth, max_iter, min_leaf in product(
            hgb_cfg.get("learning_rate", [0.1]),
            hgb_cfg.get("max_depth", [3]),
            hgb_cfg.get("max_iter", [200]),
            hgb_cfg.get("min_samples_leaf", [20]),
        ):
            params = {
                "learning_rate": float(learning_rate),
                "max_depth": int(max_depth),
                "max_iter": int(max_iter),
                "min_samples_leaf": int(min_leaf),
            }
            estimator = HistGradientBoostingClassifier(
                learning_rate=float(learning_rate),
                max_depth=int(max_depth),
                max_iter=int(max_iter),
                min_samples_leaf=int(min_leaf),
                random_state=42,
            )
            candidates["hist_gradient_boosting"].append((params, estimator, False))

    if not candidates:
        raise ValueError("No enabled models found in config")
    return candidates


def select_threshold(y_true: np.ndarray, probabilities: np.ndarray, config: dict[str, Any]) -> float:
    policy = config.get("threshold_policy", {})
    start = float(policy.get("start", 0.10))
    stop = float(policy.get("stop", 0.90))
    step = float(policy.get("step", 0.01))
    target_recall = float(policy.get("target_recall", 0.75))

    thresholds = np.arange(start, stop + (step / 2), step)
    qualified: list[tuple[float, float, float, float]] = []
    all_scores: list[tuple[float, float, float, float]] = []

    for threshold in thresholds:
        preds = (probabilities >= threshold).astype(int)
        precision = precision_score(y_true, preds, zero_division=0)
        recall = recall_score(y_true, preds, zero_division=0)
        f1 = f1_score(y_true, preds, zero_division=0)
        all_scores.append((float(threshold), float(precision), float(recall), float(f1)))
        if recall >= target_recall:
            qualified.append((float(threshold), float(precision), float(recall), float(f1)))

    if qualified:
        qualified.sort(key=lambda item: (item[1], item[3], -item[0]), reverse=True)
        return qualified[0][0]

    all_scores.sort(key=lambda item: (item[3], item[1], item[2], -item[0]), reverse=True)
    return all_scores[0][0]


def metric_bundle(y_true: np.ndarray, probabilities: np.ndarray, threshold: float) -> dict[str, Any]:
    preds = (probabilities >= threshold).astype(int)
    matrix = confusion_matrix(y_true, preds).tolist()
    return {
        "threshold": float(threshold),
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "pr_auc": float(average_precision_score(y_true, probabilities)),
        "accuracy": float(accuracy_score(y_true, preds)),
        "precision": float(precision_score(y_true, preds, zero_division=0)),
        "recall": float(recall_score(y_true, preds, zero_division=0)),
        "f1": float(f1_score(y_true, preds, zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, preds)),
        "brier_score": float(brier_score_loss(y_true, probabilities)),
        "confusion_matrix": matrix,
    }


def compute_sector_reference(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for sector, group in df.groupby("sector"):
        result[str(sector)] = {}
        for feature in REFERENCE_FEATURES:
            if feature in group.columns:
                series = pd.to_numeric(group[feature], errors="coerce")
                if not series.notna().any():
                    continue
                median = series.median()
                if pd.notna(median):
                    result[str(sector)][feature] = float(median)
    return result


def fit_and_select_model(
    model_name: str,
    candidates: list[tuple[dict[str, Any], Any, bool]],
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    numeric_columns: list[str],
    categorical_columns: list[str],
    sector_categories: list[str],
    label_column: str,
    config: dict[str, Any],
    dataset_sha256: str,
    sector_reference: dict[str, dict[str, float]],
) -> TrainedModelResult:
    x_train = train_df[numeric_columns + categorical_columns].copy()
    y_train = train_df[label_column].to_numpy()
    x_val = val_df[numeric_columns + categorical_columns].copy()
    y_val = val_df[label_column].to_numpy()
    x_test = test_df[numeric_columns + categorical_columns].copy()
    y_test = test_df[label_column].to_numpy()

    best_record: TrainedModelResult | None = None

    for params, estimator, scale_numeric in candidates:
        preprocessor = build_preprocessor(numeric_columns, categorical_columns, sector_categories, scale_numeric)
        pipeline = Pipeline(
            [
                ("preprocessor", preprocessor),
                ("classifier", estimator),
            ]
        )
        pipeline.fit(x_train, y_train)
        val_probs = pipeline.predict_proba(x_val)[:, 1]
        threshold = select_threshold(y_val, val_probs, config)
        val_metrics = metric_bundle(y_val, val_probs, threshold)

        test_probs = pipeline.predict_proba(x_test)[:, 1]
        test_metrics = metric_bundle(y_test, test_probs, threshold)

        transformed_feature_names = [
            str(name) for name in pipeline.named_steps["preprocessor"].get_feature_names_out()
        ]

        bundle = {
            "model_name": model_name,
            "model_version": str(config.get("version", "v1")),
            "trained_at": utc_now(),
            "pipeline": pipeline,
            "input_columns": numeric_columns + categorical_columns,
            "numeric_columns": numeric_columns,
            "categorical_columns": categorical_columns,
            "sector_categories": sector_categories,
            "transformed_feature_names": transformed_feature_names,
            "threshold": float(threshold),
            "dataset_sha256": dataset_sha256,
            "feature_list_version": str(config.get("version", "v1")),
            "threshold_version": str(config.get("version", "v1")),
            "sector_reference": sector_reference,
            "params": params,
        }

        record = TrainedModelResult(
            model_name=model_name,
            bundle=bundle,
            validation_metrics=val_metrics,
            test_metrics=test_metrics,
            params=params,
        )

        if best_record is None:
            best_record = record
            continue

        current = best_record.validation_metrics
        candidate_score = (
            val_metrics["pr_auc"],
            -val_metrics["brier_score"],
            -MODEL_PRIORITY[model_name],
        )
        best_score = (
            current["pr_auc"],
            -current["brier_score"],
            -MODEL_PRIORITY[model_name],
        )
        if candidate_score > best_score:
            best_record = record

    if best_record is None:
        raise RuntimeError(f"No model could be trained for {model_name}")
    return best_record


def save_feature_diagnostics(bundle: dict[str, Any], report_dir: Path) -> None:
    model_name = str(bundle["model_name"])
    classifier = bundle["pipeline"].named_steps["classifier"]
    feature_names = bundle["transformed_feature_names"]

    if hasattr(classifier, "coef_"):
        coef_df = pd.DataFrame(
            {
                "feature": feature_names,
                "coefficient": classifier.coef_[0],
                "abs_coefficient": np.abs(classifier.coef_[0]),
            }
        ).sort_values("abs_coefficient", ascending=False)
        coef_df.to_csv(report_dir / f"{model_name}_coefficients.csv", index=False)

    if hasattr(classifier, "feature_importances_"):
        imp_df = pd.DataFrame(
            {
                "feature": feature_names,
                "importance": classifier.feature_importances_,
            }
        ).sort_values("importance", ascending=False)
        imp_df.to_csv(report_dir / f"{model_name}_feature_importance.csv", index=False)


def save_artifacts(results: list[TrainedModelResult], config: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    art_cfg = config.get("artifacts", {})
    model_dir = PROJECT_ROOT / str(art_cfg.get("model_dir", "artifacts/models"))
    report_dir = PROJECT_ROOT / str(art_cfg.get("report_dir", "artifacts/reports"))
    production_alias_file = PROJECT_ROOT / str(
        art_cfg.get("production_alias_file", "artifacts/models/production_model.json")
    )

    model_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    validation_metrics: dict[str, Any] = {}
    test_metrics: dict[str, Any] = {}
    leaderboard_rows: list[dict[str, Any]] = []
    artifact_manifest: dict[str, Any] = {}

    for result in results:
        model_name = result.model_name
        model_path = model_dir / f"{model_name}.joblib"
        threshold_path = model_dir / f"{model_name}_threshold.json"
        features_path = model_dir / f"{model_name}_features.json"

        joblib.dump(result.bundle, model_path)
        threshold_payload = {
            "model_name": model_name,
            "threshold": result.bundle["threshold"],
            "threshold_version": result.bundle["threshold_version"],
        }
        features_payload = {
            "model_name": model_name,
            "input_columns": result.bundle["input_columns"],
            "numeric_columns": result.bundle["numeric_columns"],
            "categorical_columns": result.bundle["categorical_columns"],
            "transformed_feature_names": result.bundle["transformed_feature_names"],
            "feature_list_version": result.bundle["feature_list_version"],
        }
        threshold_path.write_text(json.dumps(threshold_payload, indent=2), encoding="utf-8")
        features_path.write_text(json.dumps(features_payload, indent=2), encoding="utf-8")
        save_feature_diagnostics(result.bundle, report_dir)

        validation_metrics[model_name] = result.validation_metrics
        test_metrics[model_name] = result.test_metrics
        artifact_manifest[model_name] = {
            "model_path": str(model_path),
            "threshold_path": str(threshold_path),
            "features_path": str(features_path),
            "model_version": result.bundle["model_version"],
            "dataset_sha256": result.bundle["dataset_sha256"],
            "feature_list_version": result.bundle["feature_list_version"],
            "threshold_version": result.bundle["threshold_version"],
            "params": result.params,
        }
        leaderboard_rows.append(
            {
                "model_name": model_name,
                "threshold": result.bundle["threshold"],
                "validation_pr_auc": result.validation_metrics["pr_auc"],
                "validation_roc_auc": result.validation_metrics["roc_auc"],
                "validation_brier_score": result.validation_metrics["brier_score"],
                "validation_precision": result.validation_metrics["precision"],
                "validation_recall": result.validation_metrics["recall"],
                "validation_f1": result.validation_metrics["f1"],
                "test_pr_auc": result.test_metrics["pr_auc"],
                "test_roc_auc": result.test_metrics["roc_auc"],
                "test_brier_score": result.test_metrics["brier_score"],
                "test_precision": result.test_metrics["precision"],
                "test_recall": result.test_metrics["recall"],
                "test_f1": result.test_metrics["f1"],
            }
        )

    leaderboard = pd.DataFrame(leaderboard_rows)
    leaderboard.to_csv(report_dir / "model_leaderboard.csv", index=False)
    (report_dir / "validation_metrics.json").write_text(json.dumps(validation_metrics, indent=2), encoding="utf-8")
    (report_dir / "test_metrics.json").write_text(json.dumps(test_metrics, indent=2), encoding="utf-8")

    production = choose_production_model(leaderboard, artifact_manifest)
    production_alias_file.parent.mkdir(parents=True, exist_ok=True)
    production_alias_file.write_text(json.dumps(production, indent=2), encoding="utf-8")
    return leaderboard, production


def choose_production_model(leaderboard: pd.DataFrame, artifact_manifest: dict[str, Any]) -> dict[str, Any]:
    best_pr = leaderboard["validation_pr_auc"].max()
    close = leaderboard[best_pr - leaderboard["validation_pr_auc"] <= 0.02].copy()
    close.sort_values(
        by=["validation_brier_score", "model_name"],
        inplace=True,
        key=lambda col: col.map(MODEL_PRIORITY) if col.name == "model_name" else col,
    )

    best_brier = close["validation_brier_score"].min()
    close = close[close["validation_brier_score"] == best_brier].copy()
    close["priority"] = close["model_name"].map(MODEL_PRIORITY)
    close.sort_values(by=["priority", "validation_pr_auc"], ascending=[True, False], inplace=True)
    winner_name = str(close.iloc[0]["model_name"])

    winner = artifact_manifest[winner_name].copy()
    winner["model_name"] = winner_name
    return winner


def print_summary(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame, leaderboard: pd.DataFrame, production: dict[str, Any]) -> None:
    print(f"Train rows: {len(train_df)}")
    print(f"Validation rows: {len(val_df)}")
    print(f"Test rows: {len(test_df)}")
    print("Leaderboard:")
    print(leaderboard.to_string(index=False))
    print(f"Production model: {production['model_name']}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Train and compare Fulcrum V1 models")
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Training matrix CSV")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Training config YAML")
    args = ap.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Training matrix not found: {args.input}")
    if not args.config.exists():
        raise FileNotFoundError(f"Config not found: {args.config}")

    config = load_config(args.config)
    df = pd.read_csv(args.input)
    validate_dataset(df, config)

    dataset_cfg = config.get("dataset", {})
    label_column = str(dataset_cfg.get("label_column", "target_wilful_default"))
    categorical_columns = list(dataset_cfg.get("categorical_columns", ["sector"]))

    train_df, val_df, test_df = split_by_company(df, config)
    numeric_columns = select_numeric_features(train_df.copy(), df.copy(), config)
    sector_categories = sorted(df["sector"].dropna().astype(str).str.strip().unique().tolist())
    dataset_hash = sha256_for_file(args.input)
    sector_reference = compute_sector_reference(df.copy())

    results: list[TrainedModelResult] = []
    candidates = build_model_candidates(config)
    for model_name, model_candidates in candidates.items():
        results.append(
            fit_and_select_model(
                model_name=model_name,
                candidates=model_candidates,
                train_df=train_df.copy(),
                val_df=val_df.copy(),
                test_df=test_df.copy(),
                numeric_columns=numeric_columns,
                categorical_columns=categorical_columns,
                sector_categories=sector_categories,
                label_column=label_column,
                config=config,
                dataset_sha256=dataset_hash,
                sector_reference=sector_reference,
            )
        )

    leaderboard, production = save_artifacts(results, config)
    print_summary(train_df, val_df, test_df, leaderboard, production)


if __name__ == "__main__":
    main()
