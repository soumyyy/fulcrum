"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { fetchCompanies, fetchDecisioningSummary } from "./api";
import type { DecisioningCompany, DecisioningSummary } from "./types";

const BUCKET_ORDER = ["urgent_review", "review", "manual_check", "watchlist", "monitor"];
const BUCKET_LABELS: Record<string, string> = {
  urgent_review: "Urgent review",
  review: "Review",
  manual_check: "Manual check",
  watchlist: "Watchlist",
  monitor: "Monitor",
};
const SCORE_BINS = [
  { label: "0-20", min: 0, max: 20 },
  { label: "20-40", min: 20, max: 40 },
  { label: "40-60", min: 40, max: 60 },
  { label: "60-80", min: 60, max: 80 },
  { label: "80-100", min: 80, max: 101 },
];

function formatScore(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "--";
}

function pct(value: number, total: number) {
  if (!total) return 0;
  return (value / total) * 100;
}

function splitReasons(value: string | null) {
  if (!value) return [];
  return value.split("|").map((item) => item.trim()).filter(Boolean);
}

function useModelDiagnostics() {
  const [summary, setSummary] = useState<DecisioningSummary | null>(null);
  const [companies, setCompanies] = useState<DecisioningCompany[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({ limit: "100" });
        const [summaryPayload, companiesPayload] = await Promise.all([
          fetchDecisioningSummary(controller.signal),
          fetchCompanies(params, controller.signal),
        ]);
        setSummary(summaryPayload);
        setCompanies(companiesPayload.results);
      } catch (loadError) {
        if (!controller.signal.aborted) setError(loadError instanceof Error ? loadError.message : "Failed to load diagnostics.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    load();
    return () => controller.abort();
  }, []);

  return { summary, companies, error, loading };
}

export function FulcrumWorkspace() {
  const { summary, companies, error, loading } = useModelDiagnostics();
  const total = summary?.portfolio.company_count ?? companies.length;
  const bucketRows = BUCKET_ORDER.map((bucket) => ({ bucket, count: summary?.bucket_counts?.[bucket] ?? 0 }));
  const topSectors = useMemo(() => summary?.sector_summary.slice(0, 10) ?? [], [summary]);
  const scoreBins = useMemo(
    () =>
      SCORE_BINS.map((bin) => ({
        ...bin,
        count: companies.filter((company) => company.engine_score_0_100 >= bin.min && company.engine_score_0_100 < bin.max).length,
      })),
    [companies]
  );
  const cohortStats = useMemo(() => {
    const groups = new Map<string, { count: number; total: number }>();
    for (const company of companies) {
      const key = company.cohort || "unknown";
      const item = groups.get(key) ?? { count: 0, total: 0 };
      item.count += 1;
      item.total += company.engine_score_0_100;
      groups.set(key, item);
    }
    return Array.from(groups.entries()).map(([cohort, item]) => ({ cohort, count: item.count, avg: item.count ? item.total / item.count : 0 }));
  }, [companies]);
  const reasonRows = useMemo(() => {
    const counts = new Map<string, number>();
    for (const company of companies) {
      for (const reason of splitReasons(company.top_reasons)) counts.set(reason, (counts.get(reason) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .map(([reason, count]) => ({ reason, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [companies]);
  const agreement = summary?.alignment_counts?.agree ?? 0;
  const disagreement = summary?.alignment_counts?.disagree ?? 0;
  const avgScore = companies.length ? companies.reduce((sum, company) => sum + company.engine_score_0_100, 0) / companies.length : null;

  return (
    <main className="min-h-screen overflow-hidden bg-[#07080a] text-[#f6efe2]">
      <div className="pointer-events-none fixed inset-0 opacity-90 [background:radial-gradient(circle_at_14%_10%,rgba(143,183,255,0.15),transparent_25%),radial-gradient(circle_at_82%_6%,rgba(242,236,222,0.09),transparent_24%),linear-gradient(120deg,rgba(255,255,255,0.035)_1px,transparent_1px)] [background-size:auto,auto,46px_46px]" />
      <section className="relative mx-auto flex min-h-screen w-full max-w-[1720px] flex-col gap-5 px-5 py-5 lg:px-7">
        <header className="grid gap-5 rounded-[2rem] border border-white/10 bg-[#0f1115]/92 p-5 shadow-2xl shadow-black/50 backdrop-blur-xl lg:grid-cols-[1.2fr_0.8fr]">
          <div>
            <div className="mb-4 flex flex-wrap items-center gap-3 text-[0.68rem] uppercase tracking-[0.34em] text-[#aeb7c5]">
              <span className="h-2 w-2 rounded-full bg-[#8fb7ff] shadow-[0_0_24px_rgba(143,183,255,0.9)]" />
              Fulcrum model diagnostics
              <span className="rounded-full border border-white/10 px-3 py-1 text-[#d8dee8]">historical calibration view</span>
            </div>
            <h1 className="max-w-5xl text-5xl font-semibold leading-[0.94] tracking-[-0.08em] text-white md:text-7xl">
              Understand how the risk model behaves before uploading a report.
            </h1>
            <p className="mt-5 max-w-3xl text-sm leading-7 text-[#cfd6e1]">
              This page summarizes the historical training/evaluation universe. It is not a company search surface; uploaded annual reports are analyzed separately.
            </p>
          </div>
          <div className="flex flex-col justify-between gap-4">
            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
              <MetricTile label="Sample" value={total ? String(total) : "--"} sub="companies" />
              <MetricTile label="Avg score" value={formatScore(avgScore)} sub="0-100 scale" />
              <MetricTile label="Agreement" value={agreement + disagreement ? `${formatScore(pct(agreement, agreement + disagreement))}%` : "--"} sub="primary vs benchmark" />
            </div>
            <Link className="rounded-2xl bg-[#e8edf7] px-5 py-4 text-center text-sm font-semibold text-[#090b0f] transition hover:bg-white" href="/fulcrum/report/new">
              Analyze annual report
            </Link>
          </div>
        </header>

        {error ? <StatePanel title="Diagnostics unavailable" message={error} /> : null}
        {loading ? <StatePanel title="Loading diagnostics" message="Reading model outputs and score distributions." /> : null}

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <ChartPanel title="Decision bucket distribution" kicker="operating thresholds">
            <div className="space-y-4">
              {bucketRows.map((row) => (
                <BarRow key={row.bucket} label={BUCKET_LABELS[row.bucket] ?? row.bucket} value={row.count} width={pct(row.count, total)} />
              ))}
            </div>
          </ChartPanel>

          <ChartPanel title="Score distribution" kicker="risk score bands">
            <div className="grid h-72 grid-cols-5 items-end gap-3 border-b border-white/10 pb-3">
              {scoreBins.map((bin) => {
                const maxCount = Math.max(...scoreBins.map((item) => item.count), 1);
                return (
                  <div className="flex h-full flex-col justify-end gap-2" key={bin.label}>
                    <div className="rounded-t-2xl bg-[#8fb7ff]/75" style={{ height: `${Math.max(4, pct(bin.count, maxCount))}%` }} />
                    <div className="text-center">
                      <p className="font-mono text-sm text-white">{bin.count}</p>
                      <p className="text-[0.65rem] text-[#8f98a6]">{bin.label}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </ChartPanel>

          <ChartPanel title="Cohort separation" kicker="historical label behavior">
            <div className="space-y-4">
              {cohortStats.map((row) => (
                <BarRow key={row.cohort} label={`${row.cohort} · ${row.count}`} value={Number(row.avg.toFixed(1))} width={row.avg} suffix=" avg" />
              ))}
            </div>
          </ChartPanel>

          <ChartPanel title="Top model reasons" kicker="recurring drivers">
            <div className="space-y-3">
              {reasonRows.map((row) => (
                <div className="rounded-2xl border border-white/10 bg-black/25 p-3" key={row.reason}>
                  <div className="flex justify-between gap-4 text-sm">
                    <span className="leading-5 text-[#d8dee8]">{row.reason}</span>
                    <span className="font-mono text-white">{row.count}</span>
                  </div>
                </div>
              ))}
              {!reasonRows.length ? <p className="text-sm text-[#8f98a6]">No driver data available.</p> : null}
            </div>
          </ChartPanel>
        </div>

        <ChartPanel title="Sector score heat" kicker="where risk concentrates in the training/evaluation universe">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {topSectors.map((sector) => (
              <div className="rounded-[1.25rem] border border-white/10 bg-black/25 p-4" key={sector.sector}>
                <div className="flex justify-between gap-3">
                  <p className="truncate text-sm font-semibold text-white">{sector.sector}</p>
                  <p className="font-mono text-sm text-[#d8dee8]">{formatScore(sector.avg_engine_score)}</p>
                </div>
                <div className="mt-3 h-2 rounded-full bg-white/10">
                  <div className="h-full rounded-full bg-[#8fb7ff]" style={{ width: `${Math.min(100, sector.avg_engine_score)}%` }} />
                </div>
                <p className="mt-2 text-xs text-[#8f98a6]">{sector.companies} companies · {formatScore(sector.urgent_review_rate)}% urgent historical rate</p>
              </div>
            ))}
          </div>
        </ChartPanel>
      </section>
    </main>
  );
}

function MetricTile({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-black/25 p-4">
      <p className="text-[0.65rem] uppercase tracking-[0.26em] text-[#8f98a6]">{label}</p>
      <p className="mt-2 font-mono text-3xl font-semibold text-white">{value}</p>
      <p className="mt-1 text-xs text-[#aeb7c5]">{sub}</p>
    </div>
  );
}

function ChartPanel({ title, kicker, children }: { title: string; kicker: string; children: React.ReactNode }) {
  return (
    <section className="rounded-[2rem] border border-white/10 bg-[#0e1014]/92 p-5 shadow-xl shadow-black/35">
      <p className="text-[0.65rem] uppercase tracking-[0.3em] text-[#8f98a6]">{kicker}</p>
      <h2 className="mt-2 text-3xl font-semibold tracking-[-0.06em] text-white">{title}</h2>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function BarRow({ label, value, width, suffix = "" }: { label: string; value: number; width: number; suffix?: string }) {
  return (
    <div>
      <div className="mb-2 flex justify-between gap-3 text-sm">
        <span className="truncate text-[#d8dee8]">{label}</span>
        <span className="font-mono text-white">{value}{suffix}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full bg-[#8fb7ff]" style={{ width: `${Math.min(100, width)}%` }} />
      </div>
    </div>
  );
}

function StatePanel({ title, message }: { title: string; message: string }) {
  return (
    <div className="rounded-[1.5rem] border border-white/10 bg-white/[0.05] p-5 text-[#d8dee8]">
      <p className="font-semibold text-white">{title}</p>
      <p className="mt-1 text-sm text-[#aeb7c5]">{message}</p>
    </div>
  );
}
