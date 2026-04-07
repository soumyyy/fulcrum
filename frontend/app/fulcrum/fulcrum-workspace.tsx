"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { fetchCompanies, fetchCompanyDetail, fetchDecisioningSummary } from "./api";
import type { CompanyDetailPayload, DecisionBucket, DecisioningCompany, DecisioningSummary } from "./types";

const BUCKETS = ["urgent_review", "review", "manual_check", "watchlist", "monitor"];
const BUCKET_LABELS: Record<string, string> = {
  urgent_review: "Urgent",
  review: "Review",
  manual_check: "Manual",
  watchlist: "Watchlist",
  monitor: "Monitor",
};

function formatScore(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "--";
}

function bucketTone(bucket: DecisionBucket) {
  switch (bucket) {
    case "urgent_review":
      return "border-[#ff6b35]/55 bg-[#ff6b35]/14 text-[#ffd8c5]";
    case "review":
      return "border-[#f2b84b]/55 bg-[#f2b84b]/14 text-[#ffe4aa]";
    case "manual_check":
      return "border-[#f5e6c8]/40 bg-[#f5e6c8]/10 text-[#f5e6c8]";
    case "watchlist":
      return "border-[#b9c2d0]/35 bg-white/8 text-[#e8eef7]";
    default:
      return "border-[#6f7785]/35 bg-[#11151d] text-[#cbd3df]";
  }
}

function splitReasons(value: string | null) {
  if (!value) return [];
  return value.split("|").map((item) => item.trim()).filter(Boolean);
}

function usePortfolioData(bucket: string) {
  const [summary, setSummary] = useState<DecisioningSummary | null>(null);
  const [companies, setCompanies] = useState<DecisioningCompany[]>([]);
  const [selected, setSelected] = useState<DecisioningCompany | null>(null);
  const [detail, setDetail] = useState<CompanyDetailPayload | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({ limit: "100" });
        if (bucket !== "all") params.set("bucket", bucket);
        if (query.trim()) params.set("q", query.trim());
        const [summaryPayload, companiesPayload] = await Promise.all([
          fetchDecisioningSummary(controller.signal),
          fetchCompanies(params, controller.signal),
        ]);
        setSummary(summaryPayload);
        setCompanies(companiesPayload.results);
        setSelected((current) =>
          current && companiesPayload.results.some((company) => company.cin === current.cin)
            ? current
            : companiesPayload.results[0] ?? null
        );
      } catch (loadError) {
        if (!controller.signal.aborted) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load Fulcrum data.");
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    load();
    return () => controller.abort();
  }, [bucket, query]);

  useEffect(() => {
    if (!selected?.cin) {
      setDetail(null);
      return;
    }
    const controller = new AbortController();
    fetchCompanyDetail(selected.cin, controller.signal)
      .then(setDetail)
      .catch((detailError) => {
        if (!controller.signal.aborted) {
          setError(detailError instanceof Error ? detailError.message : "Failed to load company detail.");
        }
      });
    return () => controller.abort();
  }, [selected]);

  return { summary, companies, selected, setSelected, detail, query, setQuery, error, loading };
}

export function FulcrumWorkspace() {
  const [bucket, setBucket] = useState("urgent_review");
  const { summary, companies, selected, setSelected, detail, query, setQuery, error, loading } = usePortfolioData(bucket);

  const topSectors = useMemo(() => summary?.sector_summary.slice(0, 8) ?? [], [summary]);
  const bucketTotal = useMemo(() => Object.values(summary?.bucket_counts ?? {}).reduce((sum, value) => sum + value, 0), [summary]);

  return (
    <main className="min-h-screen overflow-hidden bg-[#08090b] text-[#f7f0df]">
      <div className="pointer-events-none fixed inset-0 opacity-80 [background:radial-gradient(circle_at_15%_10%,rgba(255,107,53,0.16),transparent_26%),radial-gradient(circle_at_80%_5%,rgba(245,230,200,0.10),transparent_22%),linear-gradient(120deg,rgba(255,255,255,0.035)_1px,transparent_1px)] [background-size:auto,auto,44px_44px]" />
      <section className="relative mx-auto flex min-h-screen w-full max-w-[1720px] flex-col gap-5 px-5 py-5 lg:px-7">
        <header className="grid gap-4 rounded-[2rem] border border-white/10 bg-[#0f1115]/88 p-5 shadow-2xl shadow-black/50 backdrop-blur-xl lg:grid-cols-[1.1fr_0.9fr]">
          <div>
            <div className="mb-4 flex flex-wrap items-center gap-3 text-[0.68rem] uppercase tracking-[0.34em] text-[#b9b1a2]">
              <span className="h-2 w-2 rounded-full bg-[#ff6b35] shadow-[0_0_24px_rgba(255,107,53,0.9)]" />
              Fulcrum risk command surface
              <span className="rounded-full border border-[#f5e6c8]/20 px-3 py-1 text-[#f5e6c8]">live decisioning data</span>
            </div>
            <h1 className="max-w-5xl text-5xl font-semibold leading-[0.94] tracking-[-0.08em] text-[#fffaf0] md:text-7xl">
              Portfolio default risk, ranked for analyst action.
            </h1>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <MetricTile label="Companies" value={summary ? String(summary.portfolio.company_count) : "--"} sub="latest rows" />
            <MetricTile label="Company-years" value={summary ? String(summary.portfolio.company_year_count) : "--"} sub="audit trail" />
            <MetricTile label="Agreement" value={summary?.alignment_counts?.agree ? `${summary.alignment_counts.agree}%` : "--"} sub="engine vs audit" />
            <div className="rounded-3xl border border-[#ff6b35]/25 bg-[#ff6b35]/10 p-4 sm:col-span-2 lg:col-span-3">
              <p className="text-[0.67rem] uppercase tracking-[0.28em] text-[#f6cbb5]">Model posture</p>
              <p className="mt-2 text-sm text-[#f5e6c8]">
                Engine: <span className="text-white">{summary?.portfolio.production_model ?? "--"}</span>. Audit baseline:{" "}
                <span className="text-white">{summary?.portfolio.audit_model ?? "--"}</span>.
              </p>
            </div>
          </div>
        </header>

        <div className="grid flex-1 gap-5 xl:grid-cols-[280px_minmax(0,1fr)_420px]">
          <aside className="rounded-[2rem] border border-white/10 bg-[#101216]/90 p-4 shadow-xl shadow-black/35">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[0.65rem] uppercase tracking-[0.3em] text-[#9ba1ad]">Queue</p>
                <h2 className="mt-1 text-2xl font-semibold tracking-[-0.05em] text-white">Buckets</h2>
              </div>
              <Link className="rounded-full bg-[#ff6b35] px-4 py-2 text-xs font-semibold text-black" href="/fulcrum/report/new">
                Analyze PDF
              </Link>
            </div>
            <div className="mt-5 space-y-2">
              <BucketButton active={bucket === "all"} count={bucketTotal} label="All queues" onClick={() => setBucket("all")} />
              {BUCKETS.map((item) => (
                <BucketButton
                  key={item}
                  active={bucket === item}
                  count={summary?.bucket_counts?.[item] ?? 0}
                  label={BUCKET_LABELS[item] ?? item}
                  onClick={() => setBucket(item)}
                />
              ))}
            </div>
            <div className="mt-6 rounded-3xl border border-white/10 bg-black/20 p-4">
              <p className="text-[0.65rem] uppercase tracking-[0.28em] text-[#9ba1ad]">Sector heat</p>
              <div className="mt-4 space-y-4">
                {topSectors.map((sector) => (
                  <div key={sector.sector}>
                    <div className="mb-1 flex justify-between gap-3 text-xs text-[#d8d2c3]">
                      <span className="truncate">{sector.sector}</span>
                      <span>{formatScore(sector.urgent_review_rate)}%</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-white/10">
                      <div className="h-full rounded-full bg-[#ff6b35]" style={{ width: `${Math.min(100, sector.urgent_review_rate)}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </aside>

          <section className="min-w-0 rounded-[2rem] border border-white/10 bg-[#0e1014]/92 p-4 shadow-xl shadow-black/35">
            <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-[0.65rem] uppercase tracking-[0.3em] text-[#9ba1ad]">Action list</p>
                <h2 className="mt-1 text-3xl font-semibold tracking-[-0.06em] text-white">{BUCKET_LABELS[bucket] ?? "All"} companies</h2>
              </div>
              <input
                className="h-12 rounded-2xl border border-white/10 bg-black/35 px-4 text-sm text-white outline-none placeholder:text-[#777d88] focus:border-[#ff6b35]/70"
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search company or CIN"
                value={query}
              />
            </div>
            {error ? <StatePanel title="Backend unavailable" message={error} /> : null}
            {loading ? <StatePanel title="Loading live portfolio" message="Reading FastAPI decisioning outputs." /> : null}
            {!loading && !error && companies.length === 0 ? (
              <StatePanel title="No companies in this view" message="Change the queue or search filter." />
            ) : null}
            <div className="overflow-hidden rounded-[1.5rem] border border-white/10">
              <div className="grid grid-cols-[1.5fr_0.7fr_0.7fr_0.6fr] bg-white/[0.045] px-4 py-3 text-[0.62rem] uppercase tracking-[0.24em] text-[#9ba1ad] md:grid-cols-[1.7fr_0.8fr_0.6fr_0.6fr_0.5fr]">
                <span>Company</span>
                <span>Sector</span>
                <span>Bucket</span>
                <span>Score</span>
                <span className="hidden md:block">Rules</span>
              </div>
              <div className="max-h-[620px] overflow-auto">
                {companies.map((company) => (
                  <button
                    className={`grid w-full grid-cols-[1.5fr_0.7fr_0.7fr_0.6fr] items-center gap-3 border-t border-white/8 px-4 py-3 text-left transition hover:bg-white/[0.055] md:grid-cols-[1.7fr_0.8fr_0.6fr_0.6fr_0.5fr] ${selected?.cin === company.cin ? "bg-[#ff6b35]/10" : ""}`}
                    key={company.cin}
                    onClick={() => setSelected(company)}
                    type="button"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-semibold text-white">{company.company_name}</span>
                      <span className="block truncate font-mono text-[0.65rem] text-[#8d949f]">{company.cin}</span>
                    </span>
                    <span className="truncate text-xs text-[#d8d2c3]">{company.sector}</span>
                    <span className={`w-fit rounded-full border px-2.5 py-1 text-[0.65rem] ${bucketTone(company.decision_bucket)}`}>
                      {BUCKET_LABELS[company.decision_bucket] ?? company.decision_bucket}
                    </span>
                    <span className="font-mono text-xl font-semibold text-[#ffb38f]">{formatScore(company.engine_score_0_100)}</span>
                    <span className="hidden font-mono text-sm text-[#d8d2c3] md:block">{company.rule_flag_count}/{company.critical_rule_count}</span>
                  </button>
                ))}
              </div>
            </div>
          </section>

          <CompanyInspector company={selected} detail={detail} />
        </div>
      </section>
    </main>
  );
}

function MetricTile({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-black/25 p-4">
      <p className="text-[0.65rem] uppercase tracking-[0.26em] text-[#9ba1ad]">{label}</p>
      <p className="mt-2 font-mono text-3xl font-semibold text-white">{value}</p>
      <p className="mt-1 text-xs text-[#b9b1a2]">{sub}</p>
    </div>
  );
}

function BucketButton({ active, count, label, onClick }: { active: boolean; count: number; label: string; onClick: () => void }) {
  return (
    <button
      className={`flex w-full items-center justify-between rounded-2xl border px-4 py-3 text-sm transition ${active ? "border-[#ff6b35]/60 bg-[#ff6b35]/14 text-white" : "border-white/10 bg-white/[0.035] text-[#d8d2c3] hover:border-white/20"}`}
      onClick={onClick}
      type="button"
    >
      <span>{label}</span>
      <span className="font-mono text-[#ffb38f]">{count}</span>
    </button>
  );
}

function StatePanel({ title, message }: { title: string; message: string }) {
  return (
    <div className="mb-4 rounded-3xl border border-[#f5e6c8]/20 bg-[#f5e6c8]/8 p-5 text-[#f5e6c8]">
      <p className="font-semibold">{title}</p>
      <p className="mt-1 text-sm text-[#cfc5b1]">{message}</p>
    </div>
  );
}

function CompanyInspector({ company, detail }: { company: DecisioningCompany | null; detail: CompanyDetailPayload | null }) {
  if (!company) {
    return <aside className="rounded-[2rem] border border-white/10 bg-[#101216]/90 p-5 text-[#9ba1ad]">Select a company.</aside>;
  }
  const reasons = splitReasons(company.top_reasons);
  return (
    <aside className="rounded-[2rem] border border-white/10 bg-[#101216]/90 p-5 shadow-xl shadow-black/35">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[0.65rem] uppercase tracking-[0.3em] text-[#9ba1ad]">Inspection</p>
          <h2 className="mt-2 text-3xl font-semibold leading-none tracking-[-0.06em] text-white">{company.company_name}</h2>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs ${bucketTone(company.decision_bucket)}`}>
          {BUCKET_LABELS[company.decision_bucket] ?? company.decision_bucket}
        </span>
      </div>
      <div className="mt-6 grid grid-cols-2 gap-3">
        <MetricTile label="Engine" value={formatScore(company.engine_score_0_100)} sub={company.engine_model_name} />
        <MetricTile label="Audit" value={formatScore(company.audit_score_0_100)} sub={company.audit_model_name} />
      </div>
      <div className="mt-4 rounded-3xl border border-white/10 bg-black/25 p-4">
        <p className="text-[0.65rem] uppercase tracking-[0.28em] text-[#9ba1ad]">Support</p>
        <p className="mt-3 text-sm leading-6 text-[#ded6c5]">{company.support_summary ?? "No support summary available."}</p>
      </div>
      <div className="mt-4 rounded-3xl border border-white/10 bg-black/25 p-4">
        <p className="text-[0.65rem] uppercase tracking-[0.28em] text-[#9ba1ad]">Top reasons</p>
        <div className="mt-3 space-y-2">
          {reasons.length ? reasons.map((reason) => <p className="rounded-2xl bg-white/[0.045] px-3 py-2 text-sm text-[#f5e6c8]" key={reason}>{reason}</p>) : <p className="text-sm text-[#9ba1ad]">No reasons available.</p>}
        </div>
      </div>
      <div className="mt-4 rounded-3xl border border-white/10 bg-black/25 p-4">
        <p className="text-[0.65rem] uppercase tracking-[0.28em] text-[#9ba1ad]">Year trail</p>
        <div className="mt-3 space-y-2">
          {(detail?.years ?? []).map((year) => (
            <div className="flex items-center justify-between rounded-2xl bg-white/[0.045] px-3 py-2" key={`${year.cin}-${year.financial_year}`}>
              <span className="font-mono text-sm text-[#f5e6c8]">FY {year.financial_year}</span>
              <span className="font-mono text-sm text-[#ffb38f]">{formatScore(year.engine_score_0_100)}</span>
            </div>
          ))}
          {!detail ? <p className="text-sm text-[#9ba1ad]">Loading year history.</p> : null}
        </div>
      </div>
    </aside>
  );
}
