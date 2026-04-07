export type StatusPayload<T> = T & { status?: string; detail?: string };

export type DecisionBucket = "urgent_review" | "review" | "manual_check" | "watchlist" | "monitor" | string;

export type DecisioningSummary = StatusPayload<{
  portfolio: {
    company_count: number;
    company_year_count: number;
    production_model: string;
    audit_model: string;
  };
  bucket_counts: Record<string, number>;
  bucket_cohort_counts: Record<string, Record<string, number>>;
  engine_band_counts: Record<string, number>;
  alignment_counts: Record<string, number>;
  sector_summary: SectorSummary[];
}>;

export type SectorSummary = {
  sector: string;
  companies: number;
  avg_engine_score: number;
  urgent_review_rate: number;
};

export type DecisioningCompany = {
  company_name: string;
  cin: string;
  sector: string;
  cohort: string;
  financial_year: number;
  engine_probability: number;
  engine_score_0_100: number;
  engine_risk_band: string;
  audit_probability: number;
  audit_score_0_100: number;
  audit_risk_band: string;
  engine_audit_gap: number;
  model_alignment: string;
  rule_flag_count: number;
  critical_rule_count: number;
  decision_bucket: DecisionBucket;
  latest_overall_risk_percentile: number | null;
  latest_sector_risk_percentile: number | null;
  latest_engine_rank: number | null;
  imputed_feature_fraction: number | null;
  top_reasons: string | null;
  rule_flags_triggered: string | null;
  support_summary: string | null;
  engine_model_name: string;
  audit_model_name: string;
};

export type CompaniesPayload = StatusPayload<{
  total: number;
  limit: number;
  offset: number;
  results: DecisioningCompany[];
}>;

export type CompanyDetailPayload = StatusPayload<{
  company: DecisioningCompany;
  year_count: number;
  years: DecisioningCompany[];
}>;

export type ReportUploadResponse = {
  job_id: string;
  status: ReportJobStatus;
  created_at: string;
  upload_filename: string;
  status_url: string;
  events_url: string;
  result_url: string;
};

export type ReportJobStatus =
  | "queued"
  | "parsing"
  | "extracting"
  | "validating"
  | "featurizing"
  | "scoring"
  | "generating"
  | "completed"
  | "failed";

export type ReportStatusResponse = {
  job_id: string;
  status: ReportJobStatus;
  progress_pct: number;
  current_stage: string;
  message: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  error: string | null;
  warnings: string[];
};

export type ReportEvent = {
  event_id: string;
  event: string;
  created_at: string;
  job_id: string;
  data: Record<string, unknown>;
};

export type ReportSection = {
  section_id: string;
  kind: string;
  title: string;
  status: string;
  provenance: string[];
  markdown: string;
  data: Record<string, unknown>;
  source_refs: SourceRef[];
  warnings: string[];
};

export type SourceRef = {
  source_id: string;
  document_id: string;
  page: number | null;
  table_id: string | null;
  snippet: string | null;
  bounding_box: Record<string, number> | null;
};

export type ExtractedField = {
  field: string;
  value: string | number | null;
  normalized_value: string | number | null;
  unit: string | null;
  scale: string | null;
  period: string | null;
  basis: string;
  confidence: number;
  source_refs: SourceRef[];
  warnings: string[];
};

export type ValidationIssue = {
  field: string | null;
  severity: string;
  message: string;
  source_refs: SourceRef[];
};

export type FeatureValue = {
  feature: string;
  value: number | null;
  display_value: string | null;
  direction: string;
  percentile: number | null;
  prior_year_delta: number | null;
};

export type ModelOutput = {
  engine_model_name: string;
  engine_model_version: string;
  engine_probability: number;
  engine_score_0_100: number;
  engine_risk_band: string;
  audit_model_name: string;
  audit_probability: number;
  audit_score_0_100: number;
  model_alignment: string;
  decision_bucket: string;
  top_drivers: string[];
};

export type ReportJobResult = {
  job_id: string;
  status: ReportJobStatus;
  company: {
    company_name: string | null;
    cin: string | null;
    sector: string | null;
    financial_year: number | null;
    basis_preference: string;
  };
  extractions: ExtractedField[];
  validation_issues: ValidationIssue[];
  features: FeatureValue[];
  model_output: ModelOutput | null;
  benchmark_output: Record<string, unknown> | null;
  sections: ReportSection[];
  decision: {
    final_statement: string;
    confidence_statement: string;
    warnings: string[];
  } | null;
};
