#!/usr/bin/env python3
"""
Build a training-ready matrix from model_features.csv.

The training matrix preserves identifiers + label and removes raw text columns and
explicitly excluded sparse raw fields for the V1 model set.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import yaml
except ImportError:  # pragma: no cover - import guard for environments missing deps
    yaml = None


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "model_features.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "training_matrix.csv"
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "model_train_config.yaml"


def load_config(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise ImportError("PyYAML is required. Install with: pip install pyyaml")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid config format in {path}")
    return data


def build_training_matrix_df(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    dataset_cfg = config.get("dataset", {})
    id_columns = list(dataset_cfg.get("id_columns", []))
    label_column = str(dataset_cfg.get("label_column", "target_wilful_default"))
    drop_raw_text = set(dataset_cfg.get("drop_raw_text_columns", []))
    exclude_direct = set(dataset_cfg.get("exclude_direct_columns", []))

    required = id_columns + [label_column]
    missing_required = [col for col in required if col not in df.columns]
    if missing_required:
        raise ValueError(f"Missing required column(s): {missing_required}")

    excluded = drop_raw_text | exclude_direct
    feature_columns = [
        col for col in df.columns
        if col not in set(required) and col not in excluded
    ]

    final_columns = required + feature_columns
    return df.loc[:, final_columns].copy()


def print_summary(df: pd.DataFrame, original_columns: int) -> None:
    print(f"Rows: {len(df)}")
    print(f"Columns kept: {len(df.columns)}")
    print(f"Columns dropped: {original_columns - len(df.columns)}")
    print(f"Companies: {df['company_name'].nunique()}")
    print(f"Target balance: {df['target_wilful_default'].value_counts().to_dict()}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build training matrix from model features")
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input model feature CSV")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output training matrix CSV")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Training config YAML")
    args = ap.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input CSV not found: {args.input}")
    if not args.config.exists():
        raise FileNotFoundError(f"Config YAML not found: {args.config}")

    config = load_config(args.config)
    df = pd.read_csv(args.input)
    original_columns = len(df.columns)
    training_df = build_training_matrix_df(df, config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    training_df.to_csv(args.output, index=False)

    print(f"Wrote training matrix: {args.output}")
    print_summary(training_df, original_columns)


if __name__ == "__main__":
    main()
