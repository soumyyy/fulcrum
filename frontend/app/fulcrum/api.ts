import type {
  CompaniesPayload,
  CompanyDetailPayload,
  DecisioningSummary,
  ReportJobsPayload,
  ReportJobResult,
  ReportStatusResponse,
  ReportUploadResponse,
} from "./types";

async function readJson<T>(response: Response): Promise<T> {
  const payload = (await response.json()) as T & { detail?: string };
  if (!response.ok) {
    throw new Error(payload.detail ?? `Request failed with ${response.status}`);
  }
  return payload;
}

export async function fetchDecisioningSummary(signal?: AbortSignal) {
  const response = await fetch("/api/decisioning/summary", { cache: "no-store", signal });
  return readJson<DecisioningSummary>(response);
}

export async function fetchCompanies(params: URLSearchParams, signal?: AbortSignal) {
  const response = await fetch(`/api/decisioning/companies?${params.toString()}`, { cache: "no-store", signal });
  return readJson<CompaniesPayload>(response);
}

export async function fetchCompanyDetail(cin: string, signal?: AbortSignal) {
  const response = await fetch(`/api/decisioning/companies/${encodeURIComponent(cin)}`, { cache: "no-store", signal });
  return readJson<CompanyDetailPayload>(response);
}

export async function uploadReport(formData: FormData) {
  const response = await fetch("/api/reports/upload", {
    method: "POST",
    body: formData,
  });
  return readJson<ReportUploadResponse>(response);
}

export async function fetchReportJobs(signal?: AbortSignal) {
  const response = await fetch("/api/reports?limit=50", { cache: "no-store", signal });
  return readJson<ReportJobsPayload>(response);
}

export async function fetchReportStatus(jobId: string, signal?: AbortSignal) {
  const response = await fetch(`/api/reports/${encodeURIComponent(jobId)}/status`, { cache: "no-store", signal });
  return readJson<ReportStatusResponse>(response);
}

export async function fetchReportResult(jobId: string, signal?: AbortSignal) {
  const response = await fetch(`/api/reports/${encodeURIComponent(jobId)}`, { cache: "no-store", signal });
  return readJson<ReportJobResult>(response);
}
