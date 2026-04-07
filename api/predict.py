from __future__ import annotations

from functools import lru_cache
from io import StringIO
import json
from pathlib import Path
import sys
import time
from typing import Any

import pandas as pd
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scoring_utils import (  # noqa: E402
    DEFAULT_PRODUCTION_ALIAS,
    load_production_bundle,
    load_yaml,
    score_single_company,
)
from risk_decision import load_rules  # noqa: E402
from report_job_runner import (  # noqa: E402
    REPORT_JOBS_DIR,
    create_job,
    delete_job,
    read_events,
    read_job,
    read_result,
    run_report_job,
    save_upload_bytes,
)
from api.report_contract import (  # noqa: E402
    ReportJobResult,
    ReportJobStatusResponse,
    ReportUploadResponse,
)


app = FastAPI(title="Fulcrum Prediction API", version="v2")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


MODEL_DIR = PROJECT_ROOT / "artifacts" / "models"
REPORT_DIR = PROJECT_ROOT / "artifacts" / "reports"
DATA_DIR = PROJECT_ROOT / "data" / "processed"
DOCS_DIR = PROJECT_ROOT / "docs"

API_TRAIN_CONFIG = PROJECT_ROOT / "config" / "model_train_config_tier1a.yaml"
API_RULES_CONFIG = PROJECT_ROOT / "config" / "risk_rules.yaml"
DECISIONING_LATEST = DATA_DIR / "decisioning_output_latest.csv"
DECISIONING_YEARS = DATA_DIR / "decisioning_output_years.csv"
DECISIONING_REPORT = DOCS_DIR / "DECISIONING_SUMMARY_REPORT.md"


def _score_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    try:
        train_config = load_yaml(API_TRAIN_CONFIG)
        rules_config = load_rules(API_RULES_CONFIG)
        bundle, _manifest = load_production_bundle(DEFAULT_PRODUCTION_ALIAS)
        return score_single_company(df, train_config, rules_config, bundle)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _dataset_state(path: Path) -> tuple[str, int]:
    stat = path.stat()
    return (str(path), stat.st_mtime_ns)


@lru_cache(maxsize=4)
def _read_csv_cached(path_str: str, mtime_ns: int) -> pd.DataFrame:
    del mtime_ns
    return pd.read_csv(path_str)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required data file not found: {path}")
    return _read_csv_cached(*_dataset_state(path)).copy()


@lru_cache(maxsize=2)
def _read_text_cached(path_str: str, mtime_ns: int) -> str:
    del mtime_ns
    return Path(path_str).read_text(encoding="utf-8")


def _read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Required text file not found: {path}")
    return _read_text_cached(*_dataset_state(path))


def _load_model_catalog() -> dict[str, Any]:
    leaderboard_path = REPORT_DIR / "model_leaderboard.csv"
    validation_metrics_path = REPORT_DIR / "validation_metrics.json"
    test_metrics_path = REPORT_DIR / "test_metrics.json"
    cv_summary_path = REPORT_DIR / "grouped_cv_summary.csv"

    if not leaderboard_path.exists():
        raise FileNotFoundError(
            f"Leaderboard not found: {leaderboard_path}. Train models first with scripts/train_models.py"
        )

    leaderboard = pd.read_csv(leaderboard_path)
    validation_metrics = _load_json(validation_metrics_path)
    test_metrics = _load_json(test_metrics_path)
    cv_summary = {}
    if cv_summary_path.exists():
        cv_df = pd.read_csv(cv_summary_path)
        cv_summary = {
            str(item["model_name"]): item
            for item in cv_df.to_dict(orient="records")
        }

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
                "grouped_cv_summary": cv_summary.get(model_name, {}),
            }
        )

    return {
        "status": "ok",
        "production_model": production_name,
        "model_count": len(models),
        "models": models,
    }


def _normalize_nan_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for record in records:
        clean: dict[str, Any] = {}
        for key, value in record.items():
            if pd.isna(value):
                clean[key] = None
            else:
                clean[key] = value
        out.append(clean)
    return out


def _decisioning_summary(latest_df: pd.DataFrame, years_df: pd.DataFrame) -> dict[str, Any]:
    bucket_counts = latest_df["decision_bucket"].value_counts().to_dict()
    bucket_cohort = (
        latest_df.groupby(["decision_bucket", "cohort"])
        .size()
        .unstack(fill_value=0)
        .to_dict(orient="index")
    )
    sector_summary = (
        latest_df.groupby("sector")
        .agg(
            companies=("cin", "size"),
            avg_engine_score=("engine_score_0_100", "mean"),
            urgent_review_rate=("decision_bucket", lambda s: (s == "urgent_review").mean()),
        )
        .reset_index()
        .sort_values(["urgent_review_rate", "avg_engine_score"], ascending=[False, False])
    )
    sector_summary["avg_engine_score"] = sector_summary["avg_engine_score"].round(2)
    sector_summary["urgent_review_rate"] = (sector_summary["urgent_review_rate"] * 100).round(2)

    return {
        "status": "ok",
        "portfolio": {
            "company_count": int(latest_df["cin"].nunique()),
            "company_year_count": int(len(years_df)),
            "production_model": "hist_gradient_boosting",
            "audit_model": "logistic_regression",
        },
        "bucket_counts": bucket_counts,
        "bucket_cohort_counts": bucket_cohort,
        "engine_band_counts": latest_df["engine_risk_band"].value_counts().to_dict(),
        "alignment_counts": latest_df["model_alignment"].value_counts().to_dict(),
        "sector_summary": _normalize_nan_records(sector_summary.to_dict(orient="records")),
    }


def _companies_payload(
    df: pd.DataFrame,
    q: str | None = None,
    sector: str | None = None,
    bucket: str | None = None,
    cohort: str | None = None,
    model_alignment: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    filtered = df.copy()

    if "decision_priority" not in filtered.columns:
        priority_map = {
            "urgent_review": 1,
            "review": 2,
            "manual_check": 3,
            "watchlist": 4,
            "monitor": 5,
        }
        filtered["decision_priority"] = (
            filtered["decision_bucket"].astype(str).map(priority_map).fillna(99).astype(int)
        )

    if q:
        query = q.strip().lower()
        filtered = filtered[
            filtered["company_name"].astype(str).str.lower().str.contains(query, na=False)
            | filtered["cin"].astype(str).str.lower().str.contains(query, na=False)
        ]
    if sector:
        filtered = filtered[filtered["sector"].astype(str) == sector]
    if bucket:
        filtered = filtered[filtered["decision_bucket"].astype(str) == bucket]
    if cohort:
        filtered = filtered[filtered["cohort"].astype(str) == cohort]
    if model_alignment:
        filtered = filtered[filtered["model_alignment"].astype(str) == model_alignment]

    filtered = filtered.sort_values(
        by=["decision_priority", "engine_score_0_100", "rule_flag_count", "company_name"],
        ascending=[True, False, False, True],
    )
    total = int(len(filtered))
    page = filtered.iloc[offset : offset + limit].copy()

    return {
        "status": "ok",
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": _normalize_nan_records(page.to_dict(orient="records")),
    }


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "Fulcrum Prediction API",
        "status": "ok",
        "version": "v2",
        "message": "Use /docs for interactive API docs.",
        "endpoints": [
            "/health",
            "/models",
            "/decisioning/summary",
            "/decisioning/companies",
            "/decisioning/companies/{cin}",
            "/decisioning/report",
            "/reports/upload",
            "/reports/{job_id}/status",
            "/reports/{job_id}/events",
            "/reports/{job_id}",
            "/score-company-csv",
            "/score-company-json",
        ],
    }


@app.get("/health")
def health() -> dict[str, Any]:
    try:
        bundle, manifest = load_production_bundle(DEFAULT_PRODUCTION_ALIAS)
        rules = load_rules(API_RULES_CONFIG)
        latest_df = _read_csv(DECISIONING_LATEST)
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
        "latest_company_count": int(latest_df["cin"].nunique()),
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


@app.get("/decisioning/summary")
def decisioning_summary() -> dict[str, Any]:
    try:
        latest_df = _read_csv(DECISIONING_LATEST)
        years_df = _read_csv(DECISIONING_YEARS)
        return _decisioning_summary(latest_df, years_df)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/decisioning/companies")
def decisioning_companies(
    q: str | None = Query(default=None),
    sector: str | None = Query(default=None),
    bucket: str | None = Query(default=None),
    cohort: str | None = Query(default=None),
    model_alignment: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    try:
        latest_df = _read_csv(DECISIONING_LATEST)
        return _companies_payload(
            latest_df,
            q=q,
            sector=sector,
            bucket=bucket,
            cohort=cohort,
            model_alignment=model_alignment,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/decisioning/companies/{cin}")
def decisioning_company_detail(cin: str) -> dict[str, Any]:
    try:
        latest_df = _read_csv(DECISIONING_LATEST)
        years_df = _read_csv(DECISIONING_YEARS)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    latest_match = latest_df[latest_df["cin"].astype(str) == cin].copy()
    if latest_match.empty:
        raise HTTPException(status_code=404, detail=f"Company with CIN '{cin}' not found")

    latest_row = latest_match.iloc[0].to_dict()
    year_rows = years_df[years_df["cin"].astype(str) == cin].copy()
    year_rows.sort_values("financial_year", inplace=True)

    return {
        "status": "ok",
        "company": _normalize_nan_records([latest_row])[0],
        "year_count": int(len(year_rows)),
        "years": _normalize_nan_records(year_rows.to_dict(orient="records")),
    }


@app.get("/decisioning/sectors")
def decisioning_sectors() -> dict[str, Any]:
    try:
        latest_df = _read_csv(DECISIONING_LATEST)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    sectors = sorted(latest_df["sector"].dropna().astype(str).unique().tolist())
    return {"status": "ok", "count": len(sectors), "sectors": sectors}


@app.get("/decisioning/report")
def decisioning_report() -> dict[str, Any]:
    try:
        text = _read_text(DECISIONING_REPORT)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "path": str(DECISIONING_REPORT), "markdown": text}


@app.post("/reports/upload", status_code=202, response_model=ReportUploadResponse)
async def upload_annual_report(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    company_name: str | None = Form(default=None),
    cin: str | None = Form(default=None),
    sector: str | None = Form(default=None),
    financial_year: int | None = Form(default=None),
    basis_preference: str = Form(default="standalone"),
) -> ReportUploadResponse:
    filename = file.filename or "annual_report.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")
    if basis_preference not in {"standalone", "consolidated", "auto"}:
        raise HTTPException(status_code=400, detail="basis_preference must be standalone, consolidated, or auto")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty")

    try:
        job, destination = create_job(
            upload_filename=filename,
            company_name=company_name,
            cin=cin,
            sector=sector,
            financial_year=financial_year,
            basis_preference=basis_preference,
        )
        save_upload_bytes(destination, content)
        background_tasks.add_task(run_report_job, job["job_id"])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    job_id = str(job["job_id"])
    return ReportUploadResponse(
        job_id=job_id,
        status="queued",
        created_at=str(job["created_at"]),
        upload_filename=filename,
        status_url=f"/reports/{job_id}/status",
        events_url=f"/reports/{job_id}/events",
        result_url=f"/reports/{job_id}",
    )


@app.get("/reports")
def report_jobs(limit: int = Query(default=25, ge=1, le=100)) -> dict[str, Any]:
    jobs: list[dict[str, Any]] = []
    if REPORT_JOBS_DIR.exists():
        for path in REPORT_JOBS_DIR.iterdir():
            job_path = path / "job.json"
            if not job_path.exists():
                continue
            try:
                job = json.loads(job_path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            result_path = path / "result.json"
            result: dict[str, Any] = {}
            if result_path.exists():
                try:
                    loaded = json.loads(result_path.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        result = loaded
                except Exception:  # noqa: BLE001
                    result = {}

            company = result.get("company") if isinstance(result.get("company"), dict) else job.get("company", {})
            model_output = result.get("model_output") if isinstance(result.get("model_output"), dict) else {}
            jobs.append(
                {
                    "job_id": job.get("job_id"),
                    "status": job.get("status"),
                    "progress_pct": job.get("progress_pct"),
                    "current_stage": job.get("current_stage"),
                    "message": job.get("message"),
                    "created_at": job.get("created_at"),
                    "updated_at": job.get("updated_at"),
                    "completed_at": job.get("completed_at"),
                    "upload_filename": job.get("upload_filename"),
                    "company_name": company.get("company_name"),
                    "cin": company.get("cin"),
                    "sector": company.get("sector"),
                    "financial_year": company.get("financial_year"),
                    "basis_preference": company.get("basis_preference"),
                    "decision_bucket": model_output.get("decision_bucket"),
                    "engine_score_0_100": model_output.get("engine_score_0_100"),
                    "engine_risk_band": model_output.get("engine_risk_band"),
                    "model_alignment": model_output.get("model_alignment"),
                    "has_result": bool(result),
                }
            )

    jobs.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return {"status": "ok", "count": len(jobs), "results": jobs[:limit]}


@app.get("/reports/{job_id}/status", response_model=ReportJobStatusResponse)
def report_job_status(job_id: str) -> ReportJobStatusResponse:
    try:
        job = read_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Report job '{job_id}' not found") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ReportJobStatusResponse(
        job_id=str(job["job_id"]),
        status=job["status"],
        progress_pct=int(job["progress_pct"]),
        current_stage=str(job["current_stage"]),
        message=job.get("message"),
        created_at=str(job["created_at"]),
        updated_at=str(job["updated_at"]),
        completed_at=job.get("completed_at"),
        error=job.get("error"),
        warnings=list(job.get("warnings", [])),
    )


@app.get("/reports/{job_id}/events")
def report_job_events(job_id: str) -> StreamingResponse:
    try:
        read_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Report job '{job_id}' not found") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    def event_stream():
        sent_event_ids: set[str] = set()
        for _ in range(1800):
            events = read_events(job_id)
            for event in events:
                event_id = str(event.get("event_id", ""))
                if event_id in sent_event_ids:
                    continue
                sent_event_ids.add(event_id)
                event_name = str(event.get("event", "message"))
                yield f"event: {event_name}\n"
                yield "data: " + json.dumps(event) + "\n\n"

            job = read_job(job_id)
            if job.get("status") in {"completed", "failed"} and len(sent_event_ids) >= len(events):
                break
            time.sleep(0.75)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/reports/{job_id}", response_model=ReportJobResult)
def report_job_result(job_id: str) -> ReportJobResult:
    try:
        job = read_job(job_id)
        if job["status"] != "completed":
            raise HTTPException(status_code=409, detail=f"Report job is not complete: {job['status']}")
        result = read_result(job_id)
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Report job '{job_id}' not found") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ReportJobResult(**result)


@app.get("/reports/{job_id}/sections")
def report_job_sections(job_id: str) -> dict[str, Any]:
    result = report_job_result(job_id)
    return {"status": "ok", "job_id": job_id, "sections": [item.model_dump() for item in result.sections]}


@app.get("/reports/{job_id}/evidence")
def report_job_evidence(job_id: str) -> dict[str, Any]:
    result = report_job_result(job_id)
    return {
        "status": "ok",
        "job_id": job_id,
        "extractions": [item.model_dump() for item in result.extractions],
        "validation_issues": [item.model_dump() for item in result.validation_issues],
    }


@app.get("/reports/{job_id}/features")
def report_job_features(job_id: str) -> dict[str, Any]:
    result = report_job_result(job_id)
    return {"status": "ok", "job_id": job_id, "features": [item.model_dump() for item in result.features]}


@app.get("/reports/{job_id}/decision")
def report_job_decision(job_id: str) -> dict[str, Any]:
    result = report_job_result(job_id)
    if result.decision is None:
        raise HTTPException(status_code=409, detail="Report decision is not available yet")
    return {"status": "ok", "job_id": job_id, "decision": result.decision.model_dump()}


@app.delete("/reports/{job_id}")
def report_job_delete(job_id: str) -> dict[str, Any]:
    try:
        delete_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Report job '{job_id}' not found") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "job_id": job_id, "deleted": True}


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
