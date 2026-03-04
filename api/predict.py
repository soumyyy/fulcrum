from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scoring_utils import (  # noqa: E402
    DEFAULT_PRODUCTION_ALIAS,
    DEFAULT_RULES_CONFIG,
    DEFAULT_TRAIN_CONFIG,
    load_production_bundle,
    load_yaml,
    score_single_company,
)
from risk_decision import load_rules  # noqa: E402


app = FastAPI(title="Fulcrum Prediction API", version="v1")


MODEL_DIR = PROJECT_ROOT / "artifacts" / "models"
REPORT_DIR = PROJECT_ROOT / "artifacts" / "reports"


def _score_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    try:
        train_config = load_yaml(DEFAULT_TRAIN_CONFIG)
        rules_config = load_rules(DEFAULT_RULES_CONFIG)
        bundle, _manifest = load_production_bundle(DEFAULT_PRODUCTION_ALIAS)
        return score_single_company(df, train_config, rules_config, bundle)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _load_model_catalog() -> dict[str, Any]:
    leaderboard_path = REPORT_DIR / "model_leaderboard.csv"
    validation_metrics_path = REPORT_DIR / "validation_metrics.json"
    test_metrics_path = REPORT_DIR / "test_metrics.json"

    if not leaderboard_path.exists():
        raise FileNotFoundError(
            f"Leaderboard not found: {leaderboard_path}. Train models first with scripts/train_models.py"
        )

    leaderboard = pd.read_csv(leaderboard_path)
    validation_metrics = _load_json(validation_metrics_path)
    test_metrics = _load_json(test_metrics_path)
    _bundle, production_manifest = load_production_bundle(DEFAULT_PRODUCTION_ALIAS)
    production_name = str(production_manifest.get("model_name", "")).strip()

    models: list[dict[str, Any]] = []
    for row in leaderboard.to_dict(orient="records"):
        model_name = str(row.get("model_name", "")).strip()
        threshold_file = MODEL_DIR / f"{model_name}_threshold.json"
        features_file = MODEL_DIR / f"{model_name}_features.json"
        model_file = MODEL_DIR / f"{model_name}.joblib"

        models.append(
            {
                "model_name": model_name,
                "is_production": model_name == production_name,
                "artifact_paths": {
                    "model": str(model_file),
                    "threshold": str(threshold_file),
                    "features": str(features_file),
                },
                "leaderboard_metrics": row,
                "threshold_config": _load_json(threshold_file),
                "feature_config": _load_json(features_file),
                "validation_metrics": validation_metrics.get(model_name, {}),
                "test_metrics": test_metrics.get(model_name, {}),
            }
        )

    return {
        "status": "ok",
        "production_model": production_name,
        "model_count": len(models),
        "models": models,
    }


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "Fulcrum Prediction API",
        "status": "ok",
        "message": "Use /docs for interactive API docs, /health for service status, and /models for model comparison.",
        "endpoints": ["/health", "/models", "/score-company-csv", "/score-company-json", "/docs"],
    }


@app.get("/health")
def health() -> dict[str, Any]:
    try:
        bundle, manifest = load_production_bundle(DEFAULT_PRODUCTION_ALIAS)
        rules = load_rules(DEFAULT_RULES_CONFIG)
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}

    return {
        "status": "ok",
        "model_name": bundle.get("model_name"),
        "model_version": bundle.get("model_version"),
        "feature_list_version": bundle.get("feature_list_version"),
        "threshold_version": bundle.get("threshold_version"),
        "training_dataset_sha256": bundle.get("dataset_sha256"),
        "rule_set_version": rules.get("version"),
        "manifest": manifest,
    }


@app.get("/models")
def models() -> dict[str, Any]:
    try:
        return _load_model_catalog()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/models/{model_name}")
def model_detail(model_name: str) -> dict[str, Any]:
    try:
        catalog = _load_model_catalog()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    for model in catalog["models"]:
        if model["model_name"] == model_name:
            return model
    raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")


@app.post("/score-company-csv")
async def score_company_csv(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV uploads are supported")
    content = await file.read()
    try:
        df = pd.read_csv(StringIO(content.decode("utf-8")))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid CSV file: {exc}") from exc
    return _score_dataframe(df)


@app.post("/score-company-json")
async def score_company_json(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("rows", payload)
    if isinstance(rows, dict):
        df = pd.DataFrame([rows])
    elif isinstance(rows, list):
        df = pd.DataFrame(rows)
    else:
        raise HTTPException(status_code=400, detail="JSON payload must be an object or contain a 'rows' list")
    return _score_dataframe(df)
