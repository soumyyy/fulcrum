"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { fetchReportResult, fetchReportStatus } from "../../api";
import type { ReportEvent, ReportJobResult, ReportSection, ReportStatusResponse } from "../../types";

const PIPELINE_STAGES = [
  { label: "Uploading annual report", threshold: 0 },
  { label: "Parsing document structure", threshold: 15 },
  { label: "Extracting financial fields", threshold: 35 },
  { label: "Normalizing units and reporting basis", threshold: 55 },
  { label: "Calculating ratios", threshold: 70 },
  { label: "Running risk models", threshold: 82 },
  { label: "Generating expert report", threshold: 92 },
  { label: "Ready for review", threshold: 100 },
];

function stageStatus(stageThreshold: number, progress: number, failed: boolean) {
  if (failed) return "failed";
  if (progress >= stageThreshold) return "complete";
  const idx = PIPELINE_STAGES.findIndex((stage) => stage.threshold === stageThreshold);
  const previousThreshold = PIPELINE_STAGES[Math.max(0, idx - 1)]?.threshold ?? 0;
  if (progress >= previousThreshold) return "running";
  return "pending";
}

function markdownLite(value: string) {
  return value.replaceAll("**", "");
}

function upsertSection(current: ReportSection[], next: ReportSection) {
  const index = current.findIndex((section) => section.section_id === next.section_id);
  if (index === -1) return [...current, next];
  const copy = [...current];
  copy[index] = next;
  return copy;
}

export function ReportRunWorkspace({ jobId }: { jobId: string }) {
  const [status, setStatus] = useState<ReportStatusResponse | null>(null);
  const [result, setResult] = useState<ReportJobResult | null>(null);
  const [sections, setSections] = useState<ReportSection[]>([]);
  const [messages, setMessages] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const progress = status?.progress_pct ?? 0;
  const failed = status?.status === "failed";

  useEffect(() => {
    const eventSource = new EventSource(`/api/reports/${encodeURIComponent(jobId)}/events`);

    function onStatus(event: MessageEvent<string>) {
      const parsed = JSON.parse(event.data) as ReportEvent;
      const data = parsed.data as Partial<ReportStatusResponse>;
      setStatus((current) => ({
        job_id: jobId,
        status: (data.status as ReportStatusResponse["status"]) ?? current?.status ?? "queued",
        progress_pct: typeof data.progress_pct === "number" ? data.progress_pct : current?.progress_pct ?? 0,
        current_stage: typeof data.current_stage === "string" ? data.current_stage : current?.current_stage ?? "queued",
        message: typeof data.message === "string" ? data.message : current?.message ?? null,
        created_at: current?.created_at ?? parsed.created_at,
        updated_at: parsed.created_at,
        completed_at: current?.completed_at ?? null,
        error: current?.error ?? null,
        warnings: current?.warnings ?? [],
      }));
    }

    function onProgress(event: MessageEvent<string>) {
      const parsed = JSON.parse(event.data) as ReportEvent;
      const message = typeof parsed.data.message === "string" ? parsed.data.message : parsed.event;
      setMessages((current) => [...current.slice(-7), message]);
    }

    function onSection(event: MessageEvent<string>) {
      const parsed = JSON.parse(event.data) as ReportEvent;
      const section = parsed.data.section as ReportSection | undefined;
      if (section) setSections((current) => upsertSection(current, section));
    }

    function onComplete() {
      fetchReportResult(jobId)
        .then((nextResult) => {
          setResult(nextResult);
          setSections(nextResult.sections);
        })
        .catch((completeError) => {
          setError(completeError instanceof Error ? completeError.message : "Failed to fetch completed report.");
        });
    }

    function onError() {
      fetchReportStatus(jobId)
        .then(setStatus)
        .catch((statusError) => {
          setError(statusError instanceof Error ? statusError.message : "Report stream failed.");
        });
    }

    eventSource.addEventListener("job.status", onStatus as EventListener);
    eventSource.addEventListener("job.progress", onProgress as EventListener);
    eventSource.addEventListener("section.complete", onSection as EventListener);
    eventSource.addEventListener("job.complete", onComplete as EventListener);
    eventSource.addEventListener("error", onError);

    return () => eventSource.close();
  }, [jobId]);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    async function poll() {
      try {
        const nextStatus = await fetchReportStatus(jobId, controller.signal);
        if (cancelled) return;
        setStatus(nextStatus);
        if (nextStatus.status === "completed") {
          const nextResult = await fetchReportResult(jobId, controller.signal);
          if (!cancelled) {
            setResult(nextResult);
            setSections(nextResult.sections);
          }
        }
      } catch (pollError) {
        if (!cancelled && !controller.signal.aborted) {
          setError(pollError instanceof Error ? pollError.message : "Failed to poll report status.");
        }
      }
    }

    poll();
    const interval = window.setInterval(poll, 2500);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
      controller.abort();
    };
  }, [jobId]);

  const activeMessage = status?.message ?? messages.at(-1) ?? "Starting annual report analysis.";
  const title = result?.company.company_name ?? "Annual report analysis";
  const finalStatement = result?.decision?.final_statement;
  const modelOutput = result?.model_output;
  const featureRows = useMemo(() => result?.features ?? [], [result]);

  return (
    <main className="min-h-screen bg-[#08090b] text-[#f7f0df]">
      <div className="pointer-events-none fixed inset-0 [background:radial-gradient(circle_at_16%_12%,rgba(255,107,53,0.18),transparent_26%),radial-gradient(circle_at_82%_14%,rgba(245,230,200,0.12),transparent_22%),linear-gradient(110deg,rgba(255,255,255,0.035)_1px,transparent_1px)] [background-size:auto,auto,48px_48px]" />
      <section className="relative mx-auto flex min-h-screen w-full max-w-[1720px] flex-col gap-5 px-5 py-5 lg:px-7">
        <header className="rounded-[2rem] border border-white/10 bg-[#101216]/92 p-5 shadow-2xl shadow-black/45">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <Link className="text-xs uppercase tracking-[0.24em] text-[#ffb38f]" href="/fulcrum/report/new">
                ← New report
              </Link>
              <p className="mt-6 text-[0.65rem] uppercase tracking-[0.32em] text-[#9ba1ad]">Streaming analysis run</p>
              <h1 className="mt-2 text-5xl font-semibold leading-[0.9] tracking-[-0.08em] text-white">{title}</h1>
              <p className="mt-3 max-w-4xl text-sm leading-6 text-[#cfc5b1]">{activeMessage}</p>
            </div>
            <div className="rounded-[1.5rem] border border-[#ff6b35]/35 bg-[#ff6b35]/10 p-4 text-right">
              <p className="text-[0.65rem] uppercase tracking-[0.24em] text-[#ffb38f]">Progress</p>
              <p className="mt-1 font-mono text-5xl font-semibold text-white">{progress}%</p>
            </div>
          </div>
          <div className="mt-5 h-2 overflow-hidden rounded-full bg-white/10">
            <div className="h-full rounded-full bg-[#ff6b35] transition-all duration-500" style={{ width: `${Math.min(100, progress)}%` }} />
          </div>
        </header>

        <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)_380px]">
          <aside className="rounded-[2rem] border border-white/10 bg-[#101216]/92 p-5 shadow-xl shadow-black/35">
            <p className="text-[0.65rem] uppercase tracking-[0.32em] text-[#9ba1ad]">Model workflow</p>
            <div className="mt-5 space-y-3">
              {PIPELINE_STAGES.map((stage) => (
                <PipelineStage key={stage.label} label={stage.label} state={stageStatus(stage.threshold, progress, failed)} />
              ))}
            </div>
            {messages.length ? (
              <div className="mt-5 rounded-3xl border border-white/10 bg-black/25 p-4">
                <p className="text-[0.65rem] uppercase tracking-[0.24em] text-[#9ba1ad]">Live notes</p>
                <div className="mt-3 space-y-2">
                  {messages.slice(-5).map((message, index) => (
                    <p className="text-xs leading-5 text-[#cfc5b1]" key={`${message}-${index}`}>{message}</p>
                  ))}
                </div>
              </div>
            ) : null}
          </aside>

          <section className="rounded-[2rem] border border-white/10 bg-[#0e1014]/92 p-5 shadow-xl shadow-black/35">
            <div className="flex flex-col gap-3 border-b border-white/10 pb-5 md:flex-row md:items-end md:justify-between">
              <div>
                <p className="text-[0.65rem] uppercase tracking-[0.32em] text-[#9ba1ad]">Generated report</p>
                <h2 className="mt-2 text-4xl font-semibold tracking-[-0.07em] text-white">Sections stream in as the backend completes them.</h2>
              </div>
              {modelOutput ? (
                <div className="rounded-2xl bg-[#ff6b35] px-4 py-3 text-black">
                  <p className="text-[0.65rem] uppercase tracking-[0.22em]">Engine score</p>
                  <p className="font-mono text-3xl font-semibold">{modelOutput.engine_score_0_100.toFixed(1)}</p>
                </div>
              ) : null}
            </div>

            {error ? <Notice title="Report error" message={error} /> : null}
            {status?.status === "failed" && status.error ? <Notice title="Analysis failed" message={status.error} /> : null}

            <div className="mt-6 space-y-4">
              {sections.map((section) => (
                <article className="rounded-[1.5rem] border border-white/10 bg-black/25 p-5" key={section.section_id}>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <h3 className="text-2xl font-semibold tracking-[-0.05em] text-white">{section.title}</h3>
                    <div className="flex flex-wrap gap-2">
                      {section.provenance.map((item) => (
                        <span className="rounded-full border border-white/10 px-3 py-1 text-[0.65rem] uppercase tracking-[0.18em] text-[#b9b1a2]" key={item}>{item}</span>
                      ))}
                    </div>
                  </div>
                  <p className="mt-4 whitespace-pre-line text-sm leading-7 text-[#ded6c5]">{markdownLite(section.markdown)}</p>
                </article>
              ))}
              {!sections.length ? (
                <div className="rounded-[1.5rem] border border-white/10 bg-black/20 p-8 text-center text-[#9ba1ad]">
                  Waiting for the first generated section.
                </div>
              ) : null}
            </div>

            {finalStatement ? (
              <div className="mt-6 rounded-[1.5rem] border border-[#ff6b35]/35 bg-[#ff6b35]/10 p-5">
                <p className="text-sm font-semibold text-[#fff3d7]">Final statement</p>
                <p className="mt-2 text-sm leading-7 text-[#f5e6c8]">{finalStatement}</p>
              </div>
            ) : null}
          </section>

          <aside className="rounded-[2rem] border border-white/10 bg-[#101216]/92 p-5 shadow-xl shadow-black/35">
            <p className="text-[0.65rem] uppercase tracking-[0.32em] text-[#9ba1ad]">Extracted indicators</p>
            <div className="mt-5 grid grid-cols-2 gap-3">
              <Metric label="Bucket" value={modelOutput?.decision_bucket ?? "--"} />
              <Metric label="Audit" value={modelOutput ? modelOutput.audit_score_0_100.toFixed(1) : "--"} />
            </div>
            <div className="mt-5 rounded-3xl border border-white/10 bg-black/25 p-4">
              <p className="text-[0.65rem] uppercase tracking-[0.24em] text-[#9ba1ad]">Tier 1A ratios</p>
              <div className="mt-3 space-y-2">
                {featureRows.map((feature) => (
                  <div className="flex justify-between gap-3 rounded-2xl bg-white/[0.045] px-3 py-2" key={feature.feature}>
                    <span className="truncate text-xs text-[#d8d2c3]">{feature.feature}</span>
                    <span className="font-mono text-xs text-[#ffb38f]">{feature.display_value ?? "--"}</span>
                  </div>
                ))}
                {!featureRows.length ? <p className="text-sm text-[#9ba1ad]">Ratios will appear after scoring.</p> : null}
              </div>
            </div>
            <div className="mt-5 rounded-3xl border border-white/10 bg-black/25 p-4">
              <p className="text-[0.65rem] uppercase tracking-[0.24em] text-[#9ba1ad]">Validation</p>
              <div className="mt-3 space-y-2">
                {(result?.validation_issues ?? []).map((issue) => (
                  <p className="rounded-2xl bg-white/[0.045] p-3 text-xs leading-5 text-[#d8d2c3]" key={issue.message}>{issue.message}</p>
                ))}
                {!result?.validation_issues?.length ? <p className="text-sm text-[#9ba1ad]">Validation notes will appear after extraction.</p> : null}
              </div>
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
}

function PipelineStage({ label, state }: { label: string; state: string }) {
  const tone = state === "complete" ? "bg-[#ff6b35]" : state === "running" ? "bg-[#f5e6c8]" : state === "failed" ? "bg-red-500" : "bg-white/10";
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-black/25 p-3">
      <span className={`h-8 w-8 shrink-0 rounded-full ${tone}`} />
      <div>
        <p className="text-sm font-medium text-[#f5e6c8]">{label}</p>
        <p className="text-[0.65rem] uppercase tracking-[0.22em] text-[#8d949f]">{state}</p>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-black/25 p-4">
      <p className="text-[0.65rem] uppercase tracking-[0.24em] text-[#9ba1ad]">{label}</p>
      <p className="mt-2 truncate font-mono text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

function Notice({ title, message }: { title: string; message: string }) {
  return (
    <div className="mt-6 rounded-[1.5rem] border border-[#ff6b35]/40 bg-[#ff6b35]/10 p-5">
      <p className="text-sm font-semibold text-[#fff3d7]">{title}</p>
      <p className="mt-2 text-sm leading-6 text-[#ffd8c5]">{message}</p>
    </div>
  );
}
