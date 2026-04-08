"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { fetchReportStatus } from "../../../api";
import type { ReportEvent, ReportStatusResponse } from "../../../types";

const STEPS = [
  { id: "received", label: "Document received", threshold: 0 },
  { id: "parsing", label: "Parsing document structure", threshold: 15 },
  { id: "uploading_gemini", label: "Sending to extraction engine", threshold: 38 },
  { id: "extracting", label: "Extracting financial data", threshold: 48 },
  { id: "validating", label: "Validating extracted fields", threshold: 55 },
  { id: "normalizing", label: "Normalizing monetary units", threshold: 62 },
  { id: "ratios", label: "Computing financial ratios", threshold: 70 },
  { id: "models", label: "Running risk models", threshold: 82 },
  { id: "generating", label: "Generating analyst memo", threshold: 92 },
  { id: "assembling", label: "Assembling report package", threshold: 96 },
];

type StepStatus = "completed" | "active" | "pending";

function getStepStatus(index: number, progress: number): StepStatus {
  const next = STEPS[index + 1];
  const current = STEPS[index];
  if (next ? progress >= next.threshold : progress >= 100) return "completed";
  if (progress >= current.threshold) return "active";
  return "pending";
}

export function ProcessingWorkspace({ jobId }: { jobId: string }) {
  const router = useRouter();
  const [status, setStatus] = useState<ReportStatusResponse | null>(null);
  const [done, setDone] = useState(false);
  const redirectedRef = useRef(false);

  const progress = status?.progress_pct ?? 0;
  const failed = status?.status === "failed";

  // EventSource for real-time updates
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

    function onComplete() {
      setDone(true);
    }

    function onError() {
      fetchReportStatus(jobId).then(setStatus).catch(() => null);
    }

    eventSource.addEventListener("job.status", onStatus as EventListener);
    eventSource.addEventListener("job.complete", onComplete as EventListener);
    eventSource.addEventListener("error", onError);

    return () => eventSource.close();
  }, [jobId]);

  // Polling fallback
  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    async function poll() {
      try {
        const next = await fetchReportStatus(jobId, controller.signal);
        if (cancelled) return;
        setStatus(next);
        if (next.status === "completed") setDone(true);
      } catch {
        // swallow
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

  // Redirect when done
  useEffect(() => {
    if (!done || redirectedRef.current) return;
    redirectedRef.current = true;
    const timer = setTimeout(() => {
      router.push(`/fulcrum/report/${encodeURIComponent(jobId)}`);
    }, 600);
    return () => clearTimeout(timer);
  }, [done, jobId, router]);

  const activeLabel = STEPS.find((_, i) => getStepStatus(i, progress) === "active")?.label ?? "Processing";

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-[#08090b] px-6 text-[#f6efe2]">
      <div className="pointer-events-none fixed inset-0 [background:radial-gradient(ellipse_at_50%_0%,rgba(143,183,255,0.06),transparent_60%)]" />
      <div className="pointer-events-none fixed inset-0 [background:linear-gradient(110deg,rgba(255,255,255,0.022)_1px,transparent_1px),linear-gradient(200deg,rgba(255,255,255,0.014)_1px,transparent_1px)] [background-size:56px_56px,56px_56px]" />

      <div className="relative w-full max-w-sm">
        {/* Header */}
        <div className="mb-10 text-center">
          <p className="text-xs uppercase tracking-[0.3em] text-[#8f98a6]">Analyzing report</p>
          {failed ? (
            <p className="mt-2 text-xs text-[#ff6b35]">Analysis failed</p>
          ) : done ? (
            <p className="mt-2 text-xs text-[#8fb7ff]">Opening report…</p>
          ) : (
            <p className="mt-2 text-xs text-[#9ba1ad]">{activeLabel}</p>
          )}
        </div>

        {/* Steps */}
        <div className="flex flex-col gap-0">
          {STEPS.map((step, index) => {
            const state = getStepStatus(index, progress);
            const isLast = index === STEPS.length - 1;

            return (
              <div className="flex gap-4" key={step.id}>
                {/* Track */}
                <div className="flex flex-col items-center">
                  <StepDot state={state} />
                  {!isLast && (
                    <div
                      className={`w-px flex-1 transition-colors duration-500 ${
                        state === "completed" ? "bg-white/20" : "bg-white/[0.07]"
                      }`}
                      style={{ minHeight: "1.75rem" }}
                    />
                  )}
                </div>

                {/* Label */}
                <div className={`pb-7 pt-0.5 ${isLast ? "pb-0" : ""}`}>
                  <p
                    className={`text-sm transition-colors duration-300 ${
                      state === "completed"
                        ? "text-[#9ba1ad]"
                        : state === "active"
                        ? "font-medium text-white"
                        : "text-[#3f4550]"
                    }`}
                  >
                    {step.label}
                  </p>
                  {state === "active" && !done && (
                    <span className="mt-1 flex items-center gap-1.5">
                      <span className="h-1 w-1 animate-pulse rounded-full bg-[#8fb7ff]" style={{ animationDelay: "0ms" }} />
                      <span className="h-1 w-1 animate-pulse rounded-full bg-[#8fb7ff]" style={{ animationDelay: "200ms" }} />
                      <span className="h-1 w-1 animate-pulse rounded-full bg-[#8fb7ff]" style={{ animationDelay: "400ms" }} />
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Bottom progress bar */}
        <div className="mt-10 space-y-2">
          <div className="h-px w-full overflow-hidden rounded-full bg-white/[0.07]">
            <div
              className="h-full rounded-full bg-white/25 transition-all duration-700 ease-out"
              style={{ width: `${Math.min(100, progress)}%` }}
            />
          </div>
          <div className="flex justify-between">
            <p className="font-mono text-[0.6rem] text-[#5a6070]">{progress}%</p>
            {failed ? (
              <p className="text-[0.6rem] text-[#ff6b35]">failed</p>
            ) : done ? (
              <p className="text-[0.6rem] text-[#8fb7ff]">complete</p>
            ) : (
              <p className="text-[0.6rem] text-[#5a6070]">processing</p>
            )}
          </div>
        </div>

        {failed && (
          <div className="mt-8 rounded-2xl border border-[#ff6b35]/25 bg-[#ff6b35]/[0.08] p-4 text-center">
            <p className="text-xs text-[#ffb38f]">{status?.error ?? "The analysis could not be completed."}</p>
            <a
              className="mt-3 block text-xs text-[#8f98a6] underline underline-offset-2 hover:text-white"
              href="/fulcrum"
            >
              Try again
            </a>
          </div>
        )}
      </div>
    </main>
  );
}

function StepDot({ state }: { state: StepStatus }) {
  if (state === "completed") {
    return (
      <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/[0.12]">
        <svg className="h-2.5 w-2.5 text-[#9ba1ad]" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
          <path d="M4.5 12.75l6 6 9-13.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    );
  }

  if (state === "active") {
    return (
      <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-[#8fb7ff]/40 bg-[#8fb7ff]/10">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#8fb7ff]" />
      </div>
    );
  }

  return (
    <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-white/[0.07]">
      <span className="h-1 w-1 rounded-full bg-white/10" />
    </div>
  );
}
