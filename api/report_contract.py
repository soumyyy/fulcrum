from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ReportJobStatus = Literal[
    "queued",
    "parsing",
    "extracting",
    "validating",
    "featurizing",
    "scoring",
    "generating",
    "completed",
    "failed",
]

ReportSectionKind = Literal[
    "header",
    "executive_judgment",
    "risk_snapshot",
    "financial_stress",
    "governance_audit",
    "trend_view",
    "source_evidence",
    "analyst_conclusion",
]

SectionProvenance = Literal["deterministic", "model_derived", "llm_synthesized", "source_grounded"]
Severity = Literal["info", "watch", "warning", "critical"]


class CompanyHint(BaseModel):
    company_name: str | None = None
    cin: str | None = None
    sector: str | None = None
    financial_year: int | None = None
    basis_preference: Literal["standalone", "consolidated", "auto"] = "standalone"


class ReportUploadResponse(BaseModel):
    job_id: str
    status: ReportJobStatus
    created_at: str
    upload_filename: str
    status_url: str
    events_url: str
    result_url: str


class ReportJobStatusResponse(BaseModel):
    job_id: str
    status: ReportJobStatus
    progress_pct: int = Field(ge=0, le=100)
    current_stage: str
    message: str | None = None
    created_at: str
    updated_at: str
    completed_at: str | None = None
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)


class SourceRef(BaseModel):
    source_id: str
    document_id: str
    page: int | None = None
    table_id: str | None = None
    snippet: str | None = None
    bounding_box: dict[str, float] | None = None


class ExtractedField(BaseModel):
    field: str
    value: float | str | int | None
    normalized_value: float | str | int | None = None
    unit: str | None = None
    scale: str | None = None
    period: str | None = None
    basis: Literal["standalone", "consolidated", "unknown"] = "unknown"
    confidence: float = Field(ge=0.0, le=1.0)
    source_refs: list[SourceRef] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ValidationIssue(BaseModel):
    field: str | None = None
    severity: Severity
    message: str
    source_refs: list[SourceRef] = Field(default_factory=list)


class FeatureValue(BaseModel):
    feature: str
    value: float | int | None
    display_value: str | None = None
    direction: Literal["higher_is_riskier", "lower_is_riskier", "contextual"] = "contextual"
    percentile: float | None = Field(default=None, ge=0.0, le=100.0)
    prior_year_delta: float | None = None


class ModelOutput(BaseModel):
    engine_model_name: str
    engine_model_version: str
    engine_probability: float = Field(ge=0.0, le=1.0)
    engine_score_0_100: float = Field(ge=0.0, le=100.0)
    engine_risk_band: str
    audit_model_name: str
    audit_probability: float = Field(ge=0.0, le=1.0)
    audit_score_0_100: float = Field(ge=0.0, le=100.0)
    model_alignment: Literal["agree", "disagree"]
    decision_bucket: str
    top_drivers: list[str] = Field(default_factory=list)


class BenchmarkOutput(BaseModel):
    sector: str | None = None
    overall_risk_percentile: float | None = Field(default=None, ge=0.0, le=100.0)
    sector_risk_percentile: float | None = Field(default=None, ge=0.0, le=100.0)
    peer_context: str | None = None
    benchmark_notes: list[str] = Field(default_factory=list)


class ReportSection(BaseModel):
    section_id: str
    kind: ReportSectionKind
    title: str
    status: Literal["pending", "streaming", "complete", "failed"]
    provenance: list[SectionProvenance]
    markdown: str
    data: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[SourceRef] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ReportDecision(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    job_id: str
    company: CompanyHint
    status: ReportJobStatus
    model_output: ModelOutput
    benchmark_output: BenchmarkOutput
    final_statement: str
    confidence_statement: str
    warnings: list[str] = Field(default_factory=list)


class ReportJobResult(BaseModel):
    job_id: str
    status: ReportJobStatus
    company: CompanyHint
    extractions: list[ExtractedField] = Field(default_factory=list)
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
    features: list[FeatureValue] = Field(default_factory=list)
    model_output: ModelOutput | None = None
    benchmark_output: BenchmarkOutput | None = None
    sections: list[ReportSection] = Field(default_factory=list)
    decision: ReportDecision | None = None
