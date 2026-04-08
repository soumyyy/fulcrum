"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";

import { fetchReportJobs, uploadReport } from "../../api";
import type { ReportJobSummary } from "../../types";

function formatDate(value: string | null) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function scoreLabel(value: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return value.toFixed(1);
}

const BUCKET_COLORS: Record<string, string> = {
  urgent_review: "text-[#ff6b35]",
  review: "text-[#ffb38f]",
  manual_check: "text-[#8fb7ff]",
  watchlist: "text-[#d8dee8]",
  monitor: "text-[#9ba1ad]",
};

export function ReportUploadWorkspace() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [dragging, setDragging] = useState(false);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [jobs, setJobs] = useState<ReportJobSummary[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [jobsError, setJobsError] = useState<string | null>(null);

  useEffect(() => {
    if (!sidebarOpen) return;
    const controller = new AbortController();
    fetchReportJobs(controller.signal)
      .then((payload) => setJobs(payload.results))
      .catch((err) => {
        if (!controller.signal.aborted)
          setJobsError(err instanceof Error ? err.message : "Could not load analyses.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingJobs(false);
      });
    return () => controller.abort();
  }, [sidebarOpen]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("Select an annual report PDF first.");
      return;
    }
    setSubmitting(true);
    setError(null);
    const formData = new FormData();
    formData.append("file", file, file.name);
    try {
      const upload = await uploadReport(formData);
      router.push(`/fulcrum/report/${encodeURIComponent(upload.job_id)}/processing`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
      setSubmitting(false);
    }
  }

  function handleDrop(event: React.DragEvent) {
    event.preventDefault();
    setDragging(false);
    const dropped = event.dataTransfer.files[0];
    if (dropped?.type === "application/pdf") {
      setFile(dropped);
      setError(null);
    } else {
      setError("Only PDF files are accepted.");
    }
  }

  return (
    <>
      <main className="min-h-screen bg-[#08090b] text-[#f6efe2]">
        <div className="pointer-events-none fixed inset-0 [background:linear-gradient(110deg,rgba(255,255,255,0.025)_1px,transparent_1px),linear-gradient(200deg,rgba(255,255,255,0.015)_1px,transparent_1px)] [background-size:56px_56px,56px_56px]" />
        <div className="pointer-events-none fixed inset-0 [background:radial-gradient(ellipse_at_50%_-10%,rgba(143,183,255,0.08),transparent_55%)]" />

        <div className="relative flex min-h-screen flex-col">
          {/* Top bar */}
          <header className="flex items-center justify-between px-8 py-6">
            <Link
              className="text-xs font-medium uppercase tracking-[0.28em] text-[#9ba1ad] transition hover:text-white"
              href="/fulcrum"
            >
              ← Fulcrum
            </Link>
            <button
              className="flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-xs text-[#aeb7c5] transition hover:border-white/20 hover:text-white"
              onClick={() => {
                setJobsError(null);
                setLoadingJobs(true);
                setSidebarOpen(true);
              }}
              type="button"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-[#8fb7ff]" />
              Previous analyses
            </button>
          </header>

          {/* Centered content */}
          <div className="flex flex-1 flex-col items-center justify-center px-6 pb-20">
            <p className="text-[0.62rem] uppercase tracking-[0.4em] text-[#8f98a6]">Annual report intake</p>
            <h1 className="mt-5 max-w-lg text-center text-5xl font-semibold leading-[0.92] tracking-[-0.07em] text-white">
              Drop the report.<br />Get the risk memo.
            </h1>
            <p className="mt-5 max-w-sm text-center text-sm leading-7 text-[#7f8794]">
              Extracts company identity, financials, ratios, and model score — then writes a grounded analyst memo.
            </p>

            <form className="mt-10 w-full max-w-md" onSubmit={submit}>
              {/* Upload zone */}
              <div
                className={`cursor-pointer rounded-[2rem] border transition-all duration-200 ${
                  dragging
                    ? "border-[#8fb7ff]/60 bg-[#8fb7ff]/[0.08]"
                    : file
                    ? "border-white/20 bg-white/[0.05]"
                    : "border-dashed border-white/12 bg-white/[0.025] hover:border-white/25 hover:bg-white/[0.045]"
                }`}
                onClick={() => fileInputRef.current?.click()}
                onDragLeave={() => setDragging(false)}
                onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                onDrop={handleDrop}
              >
                <div className="flex flex-col items-center justify-center gap-3 px-8 py-10">
                  {file ? (
                    <>
                      <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/12 bg-white/[0.06]">
                        <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                          <path d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </div>
                      <div className="text-center">
                        <p className="text-sm font-semibold text-white">{file.name}</p>
                        <p className="mt-1 text-xs text-[#9ba1ad]">{(file.size / 1024 / 1024).toFixed(1)} MB · PDF</p>
                      </div>
                      <button
                        className="text-xs text-[#8f98a6] underline underline-offset-2 hover:text-[#d8dee8]"
                        onClick={(e) => { e.stopPropagation(); setFile(null); setError(null); }}
                        type="button"
                      >
                        Remove
                      </button>
                    </>
                  ) : (
                    <>
                      <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.035]">
                        <svg className="h-5 w-5 text-[#9ba1ad]" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                          <path d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </div>
                      <div className="text-center">
                        <p className="text-sm font-medium text-[#d8dee8]">Click to upload or drag and drop</p>
                        <p className="mt-1 text-xs text-[#7f8794]">Annual report PDF only</p>
                      </div>
                    </>
                  )}
                </div>
                <input
                  accept="application/pdf"
                  className="sr-only"
                  onChange={(e) => { setFile(e.target.files?.[0] ?? null); setError(null); }}
                  ref={fileInputRef}
                  type="file"
                />
              </div>

              {error ? (
                <p className="mt-3 text-center text-xs text-[#ff6b35]">{error}</p>
              ) : null}

              <button
                className="mt-4 h-[52px] w-full rounded-2xl bg-[#e8edf7] text-sm font-semibold text-[#090b0f] shadow-[0_0_40px_rgba(216,222,232,0.10)] transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-35"
                disabled={submitting || !file}
                type="submit"
              >
                {submitting ? "Starting analysis…" : "Start analysis"}
              </button>
            </form>
          </div>
        </div>
      </main>

      {/* Sidebar backdrop */}
      <div
        className={`fixed inset-0 z-40 transition-all duration-300 ${sidebarOpen ? "pointer-events-auto" : "pointer-events-none"}`}
        onClick={() => setSidebarOpen(false)}
      >
        <div className={`absolute inset-0 bg-black/50 transition-opacity duration-300 ${sidebarOpen ? "opacity-100" : "opacity-0"}`} />
      </div>

      {/* Sidebar panel */}
      <aside
        className={`fixed right-0 top-0 z-50 flex h-full w-[min(440px,100vw)] flex-col border-l border-white/10 bg-[#0c0e12]/98 shadow-2xl shadow-black/70 backdrop-blur-2xl transition-transform duration-300 ease-out ${
          sidebarOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-white/10 px-6 py-5">
          <div>
            <p className="text-[0.6rem] uppercase tracking-[0.32em] text-[#8f98a6]">Report archive</p>
            <h2 className="mt-1 text-xl font-semibold tracking-[-0.04em] text-white">Previous analyses</h2>
          </div>
          <button
            className="grid h-8 w-8 place-items-center rounded-xl border border-white/10 text-[#9ba1ad] transition hover:border-white/20 hover:text-white"
            onClick={() => setSidebarOpen(false)}
            type="button"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path d="M6 18L18 6M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4">
          {loadingJobs ? (
            <div className="flex flex-col gap-2 pt-2">
              {[1, 2, 3].map((i) => (
                <div className="h-20 animate-pulse rounded-2xl bg-white/[0.04]" key={i} />
              ))}
            </div>
          ) : jobsError ? (
            <p className="pt-6 text-center text-sm text-[#9ba1ad]">{jobsError}</p>
          ) : jobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center pt-20 text-center">
              <p className="text-sm text-[#9ba1ad]">No analyses yet.</p>
              <p className="mt-2 text-xs text-[#7f8794]">Upload an annual report to get started.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {jobs.map((job) => (
                <Link
                  className="group block rounded-2xl border border-white/[0.07] bg-white/[0.025] p-4 transition hover:border-white/18 hover:bg-white/[0.055]"
                  href={`/fulcrum/report/${encodeURIComponent(job.job_id)}`}
                  key={job.job_id}
                  onClick={() => setSidebarOpen(false)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`text-[0.6rem] uppercase tracking-[0.18em] ${BUCKET_COLORS[job.decision_bucket ?? ""] ?? "text-[#8f98a6]"}`}>
                          {job.decision_bucket ?? job.status}
                        </span>
                        {job.model_alignment ? (
                          <span className="text-[0.6rem] uppercase tracking-[0.14em] text-[#5a6070]">{job.model_alignment}</span>
                        ) : null}
                      </div>
                      <p className="mt-2 truncate text-sm font-semibold text-white group-hover:text-[#e8edf7]">
                        {job.company_name ?? job.upload_filename ?? job.job_id}
                      </p>
                      <p className="mt-1 text-xs text-[#7f8794]">
                        {job.financial_year ?? "FY pending"} · {job.sector ?? "sector pending"}
                      </p>
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="font-mono text-lg font-semibold text-white">{scoreLabel(job.engine_score_0_100)}</p>
                      <p className="mt-0.5 text-[0.58rem] text-[#5a6070]">{formatDate(job.completed_at ?? job.updated_at ?? null)}</p>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
