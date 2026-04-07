"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { fetchReportJobs, uploadReport } from "../../api";
import type { ReportJobSummary } from "../../types";

function formatDate(value: string | null) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function scoreLabel(value: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return value.toFixed(1);
}

export function ReportUploadWorkspace() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [jobs, setJobs] = useState<ReportJobSummary[]>([]);
  const [jobsError, setJobsError] = useState<string | null>(null);
  const [loadingJobs, setLoadingJobs] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    fetchReportJobs(controller.signal)
      .then((payload) => {
        setJobs(payload.results);
        setJobsError(null);
      })
      .catch((jobError) => {
        if (!controller.signal.aborted) setJobsError(jobError instanceof Error ? jobError.message : "Could not load prior analyses.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingJobs(false);
      });
    return () => controller.abort();
  }, []);

  const completedJobs = useMemo(() => jobs.filter((job) => job.status === "completed" && job.has_result), [jobs]);
  const runningJobs = useMemo(() => jobs.filter((job) => !["completed", "failed"].includes(job.status)), [jobs]);

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
      router.push(`/fulcrum/report/${encodeURIComponent(upload.job_id)}`);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Upload failed.");
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#07080a] text-[#f6efe2]">
      <div className="pointer-events-none fixed inset-0 [background:radial-gradient(circle_at_18%_12%,rgba(210,224,255,0.12),transparent_24%),radial-gradient(circle_at_78%_10%,rgba(242,236,222,0.09),transparent_24%),linear-gradient(90deg,rgba(255,255,255,0.04)_1px,transparent_1px),linear-gradient(rgba(255,255,255,0.024)_1px,transparent_1px)] [background-size:auto,auto,58px_58px,58px_58px]" />
      <section className="relative mx-auto grid min-h-screen w-full max-w-[1720px] gap-5 px-5 py-5 lg:grid-cols-[minmax(420px,0.85fr)_minmax(0,1.15fr)] lg:px-7">
        <aside className="flex flex-col justify-between rounded-[2rem] border border-white/10 bg-[#101216]/95 p-5 shadow-2xl shadow-black/45">
          <div>
            <Link className="text-xs uppercase tracking-[0.24em] text-[#d8dee8]" href="/fulcrum">
              ← Portfolio
            </Link>
            <div className="mt-10">
              <p className="text-[0.65rem] uppercase tracking-[0.32em] text-[#8f98a6]">Annual report intake</p>
              <h1 className="mt-3 text-5xl font-semibold leading-[0.9] tracking-[-0.08em] text-white">
                Drop the report. Get the risk memo.
              </h1>
              <p className="mt-5 text-sm leading-7 text-[#d8d1c4]">
                Fulcrum extracts company identity, financial year, basis, sector signal, accounting fields, ratios, model score, and a grounded analyst memo. No manual company metadata required.
              </p>
            </div>

            <form className="mt-8 space-y-4" onSubmit={submit}>
              <label className="group block cursor-pointer rounded-[2rem] border border-dashed border-[#d8dee8]/35 bg-white/[0.045] p-6 text-sm text-[#f5efe4] transition hover:border-[#d8dee8]/75 hover:bg-white/[0.07]">
                <span className="block text-[0.65rem] uppercase tracking-[0.28em] text-[#b8c0cc]">Annual report PDF</span>
                <span className="mt-5 block rounded-[1.5rem] border border-white/10 bg-black/30 p-5">
                  <span className="block text-lg font-semibold tracking-[-0.04em] text-white">{file ? file.name : "Choose a PDF file"}</span>
                  <span className="mt-2 block text-xs leading-5 text-[#9da6b5]">PDF only. The analysis starts immediately after upload and streams to a dedicated report page.</span>
                </span>
                <input
                  accept="application/pdf"
                  className="sr-only"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                  type="file"
                />
              </label>
              <button
                className="h-[56px] w-full rounded-2xl bg-[#e8edf7] px-5 py-4 text-sm font-semibold text-[#090b0f] shadow-[0_0_36px_rgba(216,222,232,0.16)] transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
                disabled={submitting}
                type="submit"
              >
                {submitting ? "Creating analysis run" : "Start report analysis"}
              </button>
            </form>
            {error ? <div className="mt-4 rounded-2xl border border-[#d8dee8]/35 bg-white/[0.06] p-4 text-sm text-[#f6efe2]">{error}</div> : null}
          </div>

          <div className="mt-10 grid gap-3 sm:grid-cols-3">
            <MiniStat label="Prior runs" value={String(jobs.length)} />
            <MiniStat label="Completed" value={String(completedJobs.length)} />
            <MiniStat label="Running" value={String(runningJobs.length)} />
          </div>
        </aside>

        <section className="rounded-[2rem] border border-white/10 bg-[#0d0f13]/94 p-5 shadow-2xl shadow-black/45">
          <div className="flex flex-col gap-3 border-b border-white/10 pb-5 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-[0.65rem] uppercase tracking-[0.32em] text-[#8f98a6]">Previous analyses</p>
              <h2 className="mt-2 text-4xl font-semibold tracking-[-0.07em] text-white">Report archive</h2>
            </div>
            <p className="max-w-md text-xs leading-5 text-[#9da6b5]">Local JSON-backed history from prior annual-report runs. No database involved.</p>
          </div>

          <div className="mt-5 space-y-3">
            {loadingJobs ? <ArchivePlaceholder text="Loading prior report runs." /> : null}
            {jobsError ? <ArchivePlaceholder text={jobsError} /> : null}
            {!loadingJobs && !jobsError && jobs.length === 0 ? <ArchivePlaceholder text="No annual reports analyzed yet." /> : null}
            {jobs.map((job) => (
              <Link
                className="group grid gap-4 rounded-[1.5rem] border border-white/10 bg-black/25 p-4 transition hover:border-[#d8dee8]/45 hover:bg-white/[0.055] md:grid-cols-[1fr_auto]"
                href={`/fulcrum/report/${encodeURIComponent(job.job_id)}`}
                key={job.job_id}
              >
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-white/10 px-3 py-1 text-[0.65rem] uppercase tracking-[0.18em] text-[#aeb7c5]">{job.status}</span>
                    {job.decision_bucket ? <span className="rounded-full border border-white/10 px-3 py-1 text-[0.65rem] uppercase tracking-[0.18em] text-[#d8d1c4]">{job.decision_bucket}</span> : null}
                    {job.model_alignment ? <span className="rounded-full border border-white/10 px-3 py-1 text-[0.65rem] uppercase tracking-[0.18em] text-[#8f98a6]">{job.model_alignment}</span> : null}
                  </div>
                  <h3 className="mt-3 text-2xl font-semibold tracking-[-0.05em] text-white group-hover:text-[#e8edf7]">
                    {job.company_name ?? job.upload_filename ?? job.job_id}
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-[#bfc7d3]">
                    {job.financial_year ?? "FY pending"} · {job.sector ?? "sector pending"} · {job.upload_filename ?? "uploaded PDF"}
                  </p>
                  <p className="mt-2 font-mono text-xs text-[#7f8794]">{job.job_id}</p>
                </div>
                <div className="flex items-end justify-between gap-5 md:flex-col md:items-end">
                  <div className="text-right">
                    <p className="text-[0.65rem] uppercase tracking-[0.22em] text-[#8f98a6]">Risk score</p>
                    <p className="mt-1 font-mono text-3xl font-semibold text-white">{scoreLabel(job.engine_score_0_100)}</p>
                  </div>
                  <p className="text-xs text-[#8f98a6]">{formatDate(job.completed_at ?? job.updated_at ?? job.created_at)}</p>
                </div>
              </Link>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-black/25 p-4">
      <p className="text-[0.65rem] uppercase tracking-[0.22em] text-[#8f98a6]">{label}</p>
      <p className="mt-2 font-mono text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

function ArchivePlaceholder({ text }: { text: string }) {
  return <div className="rounded-[1.5rem] border border-white/10 bg-black/20 p-8 text-center text-sm text-[#9da6b5]">{text}</div>;
}
