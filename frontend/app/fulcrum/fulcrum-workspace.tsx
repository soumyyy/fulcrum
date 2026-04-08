"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { fetchCompanies, fetchDecisioningSummary } from "./api";
import type { DecisioningCompany, DecisioningSummary } from "./types";

const BUCKET_ORDER = ["urgent_review", "review", "manual_check", "watchlist", "monitor"] as const;

const BUCKET_META = {
  urgent_review: { label: "Urgent review",  dot: "bg-[#ef4444]", bar: "bg-[#ef4444]",  text: "text-[#ef4444]"  },
  review:        { label: "Review",          dot: "bg-[#f59e0b]", bar: "bg-[#f59e0b]",  text: "text-[#f59e0b]"  },
  manual_check:  { label: "Manual check",    dot: "bg-[#eab308]", bar: "bg-[#eab308]",  text: "text-[#eab308]"  },
  watchlist:     { label: "Watchlist",       dot: "bg-[#60a5fa]", bar: "bg-[#60a5fa]",  text: "text-[#60a5fa]"  },
  monitor:       { label: "Monitor",         dot: "bg-[#4b5563]", bar: "bg-[#6b7280]",  text: "text-[#9ca3af]"  },
} as const;

const SCORE_BINS = [
  { label: "0–20",   min: 0,  max: 20  },
  { label: "20–40",  min: 20, max: 40  },
  { label: "40–60",  min: 40, max: 60  },
  { label: "60–80",  min: 60, max: 80  },
  { label: "80–100", min: 80, max: 101 },
];

const fmt = (v: number | null | undefined, d = 1) =>
  typeof v === "number" && Number.isFinite(v) ? v.toFixed(d) : "--";

const pct = (v: number, total: number) => (total ? (v / total) * 100 : 0);

function splitReasons(v: string | null) {
  if (!v) return [];
  return v.split("|").map((s) => s.trim()).filter(Boolean);
}

function useModelDiagnostics() {
  const [summary, setSummary] = useState<DecisioningSummary | null>(null);
  const [companies, setCompanies] = useState<DecisioningCompany[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const [s, c] = await Promise.all([
          fetchDecisioningSummary(controller.signal),
          fetchCompanies(new URLSearchParams({ limit: "100" }), controller.signal),
        ]);
        if (!controller.signal.aborted) { setSummary(s); setCompanies(c.results); }
      } catch (e) {
        if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Load failed");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    })();
    return () => controller.abort();
  }, []);

  return { summary, companies, error, loading };
}

export function FulcrumWorkspace() {
  const { summary, companies, error, loading } = useModelDiagnostics();

  const total   = summary?.portfolio.company_count ?? companies.length;
  const agree   = summary?.alignment_counts?.agree ?? 0;
  const disagree = summary?.alignment_counts?.disagree ?? 0;
  const avgScore = companies.length
    ? companies.reduce((s, c) => s + c.engine_score_0_100, 0) / companies.length
    : null;

  const bucketRows = BUCKET_ORDER.map((b) => ({
    bucket: b,
    count:  summary?.bucket_counts?.[b] ?? 0,
    meta:   BUCKET_META[b],
  }));

  const scoreBins = useMemo(() =>
    SCORE_BINS.map((bin) => ({
      ...bin,
      count: companies.filter((c) => c.engine_score_0_100 >= bin.min && c.engine_score_0_100 < bin.max).length,
    })),
  [companies]);

  const cohortStats = useMemo(() => {
    const groups = new Map<string, { count: number; sum: number }>();
    for (const c of companies) {
      const k = c.cohort || "unknown";
      const g = groups.get(k) ?? { count: 0, sum: 0 };
      g.count++; g.sum += c.engine_score_0_100;
      groups.set(k, g);
    }
    return [...groups.entries()]
      .map(([cohort, g]) => ({ cohort, count: g.count, avg: g.count ? g.sum / g.count : 0 }))
      .sort((a, b) => b.avg - a.avg);
  }, [companies]);

  const reasonRows = useMemo(() => {
    const counts = new Map<string, number>();
    for (const c of companies)
      for (const r of splitReasons(c.top_reasons))
        counts.set(r, (counts.get(r) ?? 0) + 1);
    return [...counts.entries()]
      .map(([reason, count]) => ({ reason, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);
  }, [companies]);

  const topSectors = useMemo(() => summary?.sector_summary.slice(0, 10) ?? [], [summary]);
  const maxBinCount = Math.max(...scoreBins.map((b) => b.count), 1);

  return (
    <main className="min-h-screen bg-[#07080a] text-[#e2e8f0]">
      {/* Subtle grid */}
      <div className="pointer-events-none fixed inset-0 [background:linear-gradient(rgba(255,255,255,0.018)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.018)_1px,transparent_1px)] [background-size:40px_40px]" />

      <div className="relative mx-auto max-w-[1600px] px-6 py-5 lg:px-8">

        {/* ── Top bar ── */}
        <header className="mb-5 flex items-center justify-between gap-6 border-b border-white/[0.07] pb-4">
          <div className="flex items-center gap-4">
            <span className="text-[0.65rem] font-semibold uppercase tracking-[0.3em] text-[#94a3b8]">Fulcrum</span>
            <span className="h-3 w-px bg-white/10" />
            <span className="text-[0.65rem] uppercase tracking-[0.22em] text-[#475569]">Risk model · historical universe</span>
          </div>
          <div className="flex items-center gap-5">
            <StatPill label="Universe" value={total ? String(total) : "--"} unit="co." />
            <StatPill label="Avg score" value={fmt(avgScore)} />
            <StatPill
              label="Agreement"
              value={agree + disagree ? `${fmt(pct(agree, agree + disagree))}%` : "--"}
            />
            <Link
              className="rounded-lg border border-white/15 bg-white/[0.06] px-4 py-2 text-[0.72rem] font-medium text-[#e2e8f0] transition hover:bg-white/10"
              href="/fulcrum/report/new"
            >
              New analysis →
            </Link>
          </div>
        </header>

        {error   ? <Banner message={error} /> : null}
        {loading ? <Banner message="Loading…" muted /> : null}

        {/* ── Row 1: Buckets + Score histogram ── */}
        <div className="mb-4 grid gap-4 lg:grid-cols-[380px_1fr]">

          {/* Bucket table */}
          <Panel label="Action buckets" sub="engine + benchmark">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  <th className="pb-2 text-left text-[0.6rem] font-medium uppercase tracking-[0.22em] text-[#475569]">Bucket</th>
                  <th className="pb-2 text-right text-[0.6rem] font-medium uppercase tracking-[0.22em] text-[#475569]">Count</th>
                  <th className="pb-2 text-right text-[0.6rem] font-medium uppercase tracking-[0.22em] text-[#475569]">Share</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {bucketRows.map((row) => (
                  <tr key={row.bucket} className="group">
                    <td className="py-2.5">
                      <div className="flex items-center gap-2.5">
                        <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${row.meta.dot}`} />
                        <span className={`text-[0.8rem] font-medium ${row.meta.text}`}>{row.meta.label}</span>
                      </div>
                      {/* inline bar */}
                      <div className="mt-1.5 h-px w-full overflow-hidden rounded-full bg-white/[0.05]">
                        <div
                          className={`h-full rounded-full ${row.meta.bar} opacity-50 transition-all duration-700`}
                          style={{ width: `${pct(row.count, total)}%` }}
                        />
                      </div>
                    </td>
                    <td className="py-2.5 text-right font-mono text-sm text-white">{row.count}</td>
                    <td className="py-2.5 text-right font-mono text-[0.72rem] text-[#64748b]">
                      {total ? `${pct(row.count, total).toFixed(0)}%` : "--"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>

          {/* Score histogram */}
          <Panel label="Score distribution" sub="0–100 risk scale">
            <div className="flex h-48 items-end gap-2">
              {scoreBins.map((bin) => {
                const h = Math.max(2, pct(bin.count, maxBinCount));
                const isHigh = bin.min >= 60;
                const isMid  = bin.min >= 40 && bin.min < 60;
                const barCls = isHigh ? "bg-[#ef4444]/60" : isMid ? "bg-[#f59e0b]/50" : "bg-[#60a5fa]/50";
                return (
                  <div className="flex flex-1 flex-col items-center gap-1.5" key={bin.label}>
                    <span className="font-mono text-xs text-white">{bin.count}</span>
                    <div className="flex w-full items-end" style={{ height: "120px" }}>
                      <div
                        className={`w-full rounded-sm ${barCls} transition-all duration-700`}
                        style={{ height: `${h}%` }}
                      />
                    </div>
                    <span className="font-mono text-[0.6rem] text-[#475569]">{bin.label}</span>
                  </div>
                );
              })}
            </div>
            {/* Axis reference */}
            <div className="mt-4 flex items-center gap-4 border-t border-white/[0.06] pt-3 text-[0.6rem] text-[#475569]">
              <span className="flex items-center gap-1.5"><span className="h-1.5 w-3 rounded-sm bg-[#60a5fa]/50" />0–40 · low</span>
              <span className="flex items-center gap-1.5"><span className="h-1.5 w-3 rounded-sm bg-[#f59e0b]/50" />40–60 · mid</span>
              <span className="flex items-center gap-1.5"><span className="h-1.5 w-3 rounded-sm bg-[#ef4444]/60" />60–100 · high</span>
            </div>
          </Panel>
        </div>

        {/* ── Row 2: Sector table + right col (cohort + drivers) ── */}
        <div className="grid gap-4 lg:grid-cols-[1fr_320px]">

          {/* Sector table */}
          <Panel label="Sector exposure" sub="avg score · urgent rate · co. count">
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  {["Sector", "Co.", "Avg score", "Urgent %", ""].map((h, i) => (
                    <th
                      key={h || i}
                      className={`pb-2.5 text-[0.6rem] font-medium uppercase tracking-[0.22em] text-[#475569] ${i === 0 ? "text-left" : "text-right"} ${i === 4 ? "w-28" : ""}`}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {topSectors.map((s) => {
                  const score = s.avg_engine_score;
                  const urgentPct = s.urgent_review_rate ?? 0;
                  const scoreCls  = score >= 65 ? "text-[#ef4444]" : score >= 45 ? "text-[#f59e0b]" : "text-[#60a5fa]";
                  const urgentCls = urgentPct >= 30 ? "text-[#ef4444]" : "text-[#94a3b8]";
                  const barCls    = score >= 65 ? "bg-[#ef4444]/50" : score >= 45 ? "bg-[#f59e0b]/50" : "bg-[#60a5fa]/40";
                  return (
                    <tr key={s.sector} className="group">
                      <td className="py-2.5 text-[0.8rem] font-medium text-[#cbd5e1]">{s.sector}</td>
                      <td className="py-2.5 text-right font-mono text-[0.72rem] text-[#64748b]">{s.companies}</td>
                      <td className={`py-2.5 text-right font-mono text-[0.85rem] font-semibold ${scoreCls}`}>{fmt(score)}</td>
                      <td className={`py-2.5 text-right font-mono text-[0.72rem] ${urgentCls}`}>{fmt(urgentPct)}%</td>
                      <td className="py-2.5 pl-4">
                        <div className="h-1 w-full overflow-hidden rounded-full bg-white/[0.06]">
                          <div
                            className={`h-full rounded-full ${barCls} transition-all duration-700`}
                            style={{ width: `${Math.min(100, score)}%` }}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Panel>

          {/* Right column */}
          <div className="flex flex-col gap-4">

            {/* Cohort separation */}
            <Panel label="Cohort separation" sub="avg score by label">
              <div className="space-y-3">
                {cohortStats.map((row) => {
                  const barCls = row.avg >= 55 ? "bg-[#ef4444]/60" : "bg-[#60a5fa]/60";
                  return (
                    <div key={row.cohort}>
                      <div className="mb-1 flex justify-between text-[0.72rem]">
                        <span className="text-[#94a3b8]">{row.cohort} <span className="text-[#475569]">({row.count})</span></span>
                        <span className="font-mono font-semibold text-white">{row.avg.toFixed(1)}</span>
                      </div>
                      <div className="h-1 overflow-hidden rounded-full bg-white/[0.06]">
                        <div
                          className={`h-full rounded-full ${barCls} transition-all duration-700`}
                          style={{ width: `${Math.min(100, row.avg)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
                {!cohortStats.length && !loading ? (
                  <p className="text-[0.72rem] text-[#475569]">No data</p>
                ) : null}
              </div>
            </Panel>

            {/* Risk drivers */}
            <Panel label="Top risk drivers" sub="by frequency">
              <ol className="space-y-1">
                {reasonRows.map((row, i) => (
                  <li key={row.reason} className="flex items-baseline justify-between gap-3 py-1.5 border-b border-white/[0.04] last:border-0">
                    <div className="flex items-baseline gap-2 min-w-0">
                      <span className="shrink-0 font-mono text-[0.58rem] text-[#334155]">{String(i + 1).padStart(2, "0")}</span>
                      <span className="truncate text-[0.75rem] text-[#94a3b8]">{row.reason}</span>
                    </div>
                    <span className="shrink-0 font-mono text-[0.75rem] text-white">{row.count}</span>
                  </li>
                ))}
                {!reasonRows.length && !loading ? (
                  <p className="text-[0.72rem] text-[#475569]">No data</p>
                ) : null}
              </ol>
            </Panel>

          </div>
        </div>

      </div>
    </main>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────

function Panel({ label, sub, children }: { label: string; sub: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-white/[0.07] bg-[#0c0f14]/90 p-5">
      <div className="mb-4 flex items-baseline gap-2">
        <span className="text-[0.65rem] font-semibold uppercase tracking-[0.26em] text-[#64748b]">{label}</span>
        <span className="text-[0.6rem] text-[#334155]">{sub}</span>
      </div>
      {children}
    </div>
  );
}

function StatPill({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="text-[0.6rem] uppercase tracking-[0.2em] text-[#475569]">{label}</span>
      <span className="font-mono text-sm font-semibold text-white">{value}</span>
      {unit ? <span className="text-[0.6rem] text-[#475569]">{unit}</span> : null}
    </div>
  );
}

function Banner({ message, muted }: { message: string; muted?: boolean }) {
  return (
    <div className={`mb-4 rounded-lg border px-4 py-2.5 text-xs ${muted ? "border-white/[0.05] text-[#475569]" : "border-[#ef4444]/25 bg-[#ef4444]/[0.06] text-[#fca5a5]"}`}>
      {message}
    </div>
  );
}
