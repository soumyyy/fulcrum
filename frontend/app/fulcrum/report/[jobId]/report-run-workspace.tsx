"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { fetchReportResult, fetchReportStatus } from "../../api";
import type {
  ExtractedField,
  FeatureValue,
  ReportEvent,
  ReportJobResult,
  ReportSection,
  ReportStatusResponse,
} from "../../types";

// ─── Pipeline stages ────────────────────────────────────────────────────────

const PIPELINE_STAGES = [
  { label: "Uploading annual report",  threshold: 0   },
  { label: "Parsing document",         threshold: 15  },
  { label: "Extracting fields",        threshold: 35  },
  { label: "Validating values",        threshold: 55  },
  { label: "Calculating ratios",       threshold: 70  },
  { label: "Running models",           threshold: 82  },
  { label: "Generating report",        threshold: 92  },
  { label: "Ready for review",         threshold: 100 },
];

function activeWorkflow(progress: number, failed: boolean) {
  if (failed) return { label: "Analysis failed", next: "Review error" };
  const current = [...PIPELINE_STAGES].reverse().find((s) => progress >= s.threshold) ?? PIPELINE_STAGES[0];
  const next = PIPELINE_STAGES.find((s) => s.threshold > progress);
  return { label: current.label, next: next?.label ?? "Complete" };
}

// ─── Section ordering ────────────────────────────────────────────────────────

const SECTION_ORDER = [
  "company_profile",
  "model_verdict",
  "balance_sheet_risk",
  "liquidity_cash_flow",
  "profitability_asset_quality",
  "governance_audit",
];

// ─── Risk signal types ───────────────────────────────────────────────────────

type RiskSignal = "warn" | "caution" | "ok";

const SIG_VAL: Record<RiskSignal, string> = {
  warn:    "text-[#ef4444]",
  caution: "text-[#f59e0b]",
  ok:      "text-[#e2e8f0]",
};

const SIG_ROW: Record<RiskSignal, string> = {
  warn:    "border-l-2 border-l-[#ef4444]/50 bg-[#ef4444]/[0.04]",
  caution: "border-l-2 border-l-[#f59e0b]/40 bg-[#f59e0b]/[0.03]",
  ok:      "",
};

// ─── Numeric helpers ─────────────────────────────────────────────────────────

function numericField(extractions: ExtractedField[], field: string): number | null {
  const item = extractions.find((e) => e.field === field);
  const value = item?.normalized_value ?? item?.value;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value.replaceAll(",", ""));
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function rawField(extractions: ExtractedField[], field: string): string | number | null {
  const item = extractions.find((e) => e.field === field);
  return item?.value ?? null;
}

function safeRatio(a: number | null, b: number | null): number | null {
  if (a === null || b === null || b === 0) return null;
  return a / b;
}

function fmtMoney(v: number | null): string {
  if (v === null) return "—";
  const abs = Math.abs(v);
  const prefix = v < 0 ? "−" : "";
  return `${prefix}₹${abs.toLocaleString("en-IN", { maximumFractionDigits: 2 })} cr`;
}

function fmtRatio(v: number | null, decimals = 2): string {
  if (v === null) return "—";
  return v.toFixed(decimals);
}

function fmtPct(v: number | null, decimals = 1): string {
  if (v === null) return "—";
  return `${(v * 100).toFixed(decimals)}%`;
}

function fmtX(v: number | null): string {
  if (v === null) return "—";
  return `${v.toFixed(2)}×`;
}

// ─── Derived metrics ─────────────────────────────────────────────────────────

type DerivedMetrics = {
  ebt: number | null;
  effectiveTaxRate: number | null;
  freeCashFlow: number | null;
  netDebt: number | null;
  debtToEquity: number | null;
  ebitdaInterestCoverage: number | null;
  workingCapital: number | null;
  assetTurnover: number | null;
  interestToRevenue: number | null;
  ebit: number | null;
  debtToAssets: number | null;
};

function computeDerived(ex: ExtractedField[]): DerivedMetrics {
  const pat      = numericField(ex, "pat");
  const tax      = numericField(ex, "tax_expense");
  const cfo      = numericField(ex, "cfo");
  const capex    = numericField(ex, "capex");
  const borr     = numericField(ex, "total_borrowings");
  const cash     = numericField(ex, "cash_and_equivalents");
  const equity   = numericField(ex, "total_equity");
  const ebitda   = numericField(ex, "ebitda");
  const depr     = numericField(ex, "depreciation");
  const interest = numericField(ex, "interest_expense");
  const ca       = numericField(ex, "current_assets");
  const cl       = numericField(ex, "current_liabilities");
  const revenue  = numericField(ex, "revenue");
  const assets   = numericField(ex, "total_assets");

  const ebt      = pat !== null && tax !== null ? pat + tax : null;
  const ebit     = ebitda !== null && depr !== null ? ebitda - depr : null;

  return {
    ebt,
    ebit,
    effectiveTaxRate: safeRatio(tax, ebt),
    freeCashFlow:     cfo !== null && capex !== null ? cfo - Math.abs(capex) : null,
    netDebt:          borr !== null && cash !== null ? borr - cash : null,
    debtToEquity:     safeRatio(borr, equity),
    debtToAssets:     safeRatio(borr, assets),
    ebitdaInterestCoverage: safeRatio(ebitda, interest),
    workingCapital:   ca !== null && cl !== null ? ca - cl : null,
    assetTurnover:    safeRatio(revenue, assets),
    interestToRevenue: safeRatio(interest, revenue),
  };
}

// ─── Supplementary ratios ────────────────────────────────────────────────────

type SupplementaryRatio = { feature: string; label: string; value: number | null; fmt: string; signal: RiskSignal; bench: string };

function computeSupplementary(ex: ExtractedField[]): SupplementaryRatio[] {
  const ca       = numericField(ex, "current_assets");
  const cl       = numericField(ex, "current_liabilities");
  const cash     = numericField(ex, "cash_and_equivalents");
  const assets   = numericField(ex, "total_assets");
  const cont     = numericField(ex, "contingent_liabilities_amount");
  const ebitda   = numericField(ex, "ebitda");
  const interest = numericField(ex, "interest_expense");

  const cr  = safeRatio(ca, cl);
  const csr = safeRatio(cash, cl);
  const wca = ca !== null && cl !== null ? safeRatio(ca - cl, assets) : null;
  const cta = safeRatio(cont, assets);
  const ei  = safeRatio(ebitda, interest);

  return [
    { feature: "current_ratio",                   label: "Current ratio",                  value: cr,  fmt: fmtRatio(cr),   signal: cr  !== null && cr  < 1.0 ? "warn" : cr !== null && cr < 1.5 ? "caution" : "ok", bench: "Healthy ≥ 1.5" },
    { feature: "cash_ratio",                       label: "Cash ratio",                     value: csr, fmt: fmtRatio(csr),  signal: csr !== null && csr < 0.5 ? "warn" : "ok",                                        bench: "Acceptable ≥ 0.5" },
    { feature: "working_capital_to_assets",        label: "Working capital / assets",       value: wca, fmt: fmtRatio(wca),  signal: wca !== null && wca < 0   ? "warn" : "ok",                                        bench: "Positive preferred" },
    { feature: "contingent_liabilities_to_assets", label: "Contingent liabilities / assets",value: cta, fmt: fmtRatio(cta),  signal: cta !== null && cta > 0.1 ? "warn" : cta !== null && cta > 0.05 ? "caution" : "ok", bench: "Watch above 5%" },
    { feature: "ebitda_to_interest",               label: "EBITDA / interest",               value: ei,  fmt: fmtX(ei),       signal: ei  !== null && ei  < 1.5 ? "warn" : ei  !== null && ei  < 2.0 ? "caution" : "ok",  bench: "Comfortable ≥ 2×" },
  ];
}

// ─── Feature signal helpers ──────────────────────────────────────────────────

function featureSignal(f: FeatureValue): RiskSignal {
  if (typeof f.value !== "number") return "ok";
  if (f.feature === "debt_to_assets" && f.value > 0.65) return "warn";
  if (f.feature === "debt_to_assets" && f.value > 0.5)  return "caution";
  if (["ebitda_margin", "pat_margin", "roa", "cfo_to_assets"].includes(f.feature) && f.value < 0) return "warn";
  if (f.feature === "cfo_to_ebitda" && f.value < 0) return "warn";
  if (f.feature === "cfo_to_ebitda" && f.value < 0.8) return "caution";
  if (f.feature === "retained_earnings_to_assets" && f.value < 0) return "warn";
  return "ok";
}

// ─── Bucket meta ─────────────────────────────────────────────────────────────

const BUCKET_META: Record<string, { label: string; color: string }> = {
  urgent_review: { label: "Urgent review", color: "text-[#ef4444]" },
  review:        { label: "Review",         color: "text-[#f59e0b]" },
  manual_check:  { label: "Manual check",   color: "text-[#eab308]" },
  watchlist:     { label: "Watchlist",      color: "text-[#60a5fa]" },
  monitor:       { label: "Monitor",        color: "text-[#94a3b8]" },
};

const SCORE_COLOR = (score: number) =>
  score >= 65 ? "text-[#ef4444]" : score >= 45 ? "text-[#f59e0b]" : "text-[#60a5fa]";

// ─── Feature label map ───────────────────────────────────────────────────────

const FEATURE_LABELS: Record<string, { label: string; bench: string; direction: string }> = {
  debt_to_assets:               { label: "Debt / assets",               bench: "Watch > 0.50",     direction: "↑ worse" },
  ebitda_margin:                { label: "EBITDA margin",               bench: "Sector-dependent", direction: "↓ worse" },
  pat_margin:                   { label: "PAT margin",                  bench: "Positive required", direction: "↓ worse" },
  roa:                          { label: "ROA",                         bench: "~5% acceptable",   direction: "↓ worse" },
  retained_earnings_to_assets:  { label: "Retained earnings / assets",  bench: "Positive preferred",direction: "↓ worse" },
  cfo_to_assets:                { label: "CFO / assets",                bench: "Positive required", direction: "↓ worse" },
  cfo_to_ebitda:                { label: "CFO / EBITDA",               bench: "Watch < 0.8",       direction: "↓ worse" },
  net_cash_change_to_assets:    { label: "Net cash change / assets",    bench: "Positive preferred",direction: "↓ worse" },
  log_total_assets:             { label: "Scale: total assets (log)",   bench: "Scale control",     direction: "—" },
  log_revenue:                  { label: "Scale: revenue (log)",        bench: "Scale control",     direction: "—" },
};

// ─── Markdown helpers ────────────────────────────────────────────────────────

function memoBlocks(value: string) {
  return value
    .replaceAll("**", "")
    .split(/\n+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function upsertSection(current: ReportSection[], next: ReportSection) {
  const idx = current.findIndex((s) => s.section_id === next.section_id);
  if (idx === -1) return [...current, next];
  const copy = [...current]; copy[idx] = next; return copy;
}

// ─── Main component ──────────────────────────────────────────────────────────

export function ReportRunWorkspace({ jobId }: { jobId: string }) {
  const [status,   setStatus]   = useState<ReportStatusResponse | null>(null);
  const [result,   setResult]   = useState<ReportJobResult | null>(null);
  const [sections, setSections] = useState<ReportSection[]>([]);
  const [messages, setMessages] = useState<string[]>([]);
  const [error,    setError]    = useState<string | null>(null);
  const [showStatements, setShowStatements] = useState(false);

  const progress = status?.progress_pct ?? 0;
  const failed   = status?.status === "failed";

  // EventSource
  useEffect(() => {
    const es = new EventSource(`/api/reports/${encodeURIComponent(jobId)}/events`);

    es.addEventListener("job.status", ((e: MessageEvent<string>) => {
      const p = JSON.parse(e.data) as ReportEvent;
      const d = p.data as Partial<ReportStatusResponse>;
      setStatus((cur) => ({
        job_id: jobId,
        status: (d.status as ReportStatusResponse["status"]) ?? cur?.status ?? "queued",
        progress_pct: typeof d.progress_pct === "number" ? d.progress_pct : cur?.progress_pct ?? 0,
        current_stage: typeof d.current_stage === "string" ? d.current_stage : cur?.current_stage ?? "queued",
        message: typeof d.message === "string" ? d.message : cur?.message ?? null,
        created_at: cur?.created_at ?? p.created_at,
        updated_at: p.created_at,
        completed_at: cur?.completed_at ?? null,
        error: cur?.error ?? null,
        warnings: cur?.warnings ?? [],
      }));
    }) as EventListener);

    es.addEventListener("job.progress", ((e: MessageEvent<string>) => {
      const p = JSON.parse(e.data) as ReportEvent;
      const msg = typeof p.data.message === "string" ? p.data.message : p.event;
      setMessages((cur) => [...cur.slice(-9), msg]);
    }) as EventListener);

    es.addEventListener("section.complete", ((e: MessageEvent<string>) => {
      const p = JSON.parse(e.data) as ReportEvent;
      const s = p.data.section as ReportSection | undefined;
      if (s) setSections((cur) => upsertSection(cur, s));
    }) as EventListener);

    es.addEventListener("job.complete", (() => {
      fetchReportResult(jobId)
        .then((r) => { setResult(r); setSections(r.sections); })
        .catch((e) => setError(e instanceof Error ? e.message : "Failed to fetch report."));
    }) as EventListener);

    es.addEventListener("error", () => {
      fetchReportStatus(jobId).then(setStatus).catch(() => null);
    });

    return () => es.close();
  }, [jobId]);

  // Polling fallback
  useEffect(() => {
    const ctrl = new AbortController();
    let cancelled = false;

    async function poll() {
      try {
        const s = await fetchReportStatus(jobId, ctrl.signal);
        if (cancelled) return;
        setStatus(s);
        if (s.status === "completed") {
          const r = await fetchReportResult(jobId, ctrl.signal);
          if (!cancelled) { setResult(r); setSections(r.sections); }
        }
      } catch { /* swallow */ }
    }

    poll();
    const iv = window.setInterval(poll, 2500);
    return () => { cancelled = true; clearInterval(iv); ctrl.abort(); };
  }, [jobId]);

  // Derived data
  const extractions       = useMemo(() => result?.extractions ?? [],  [result]);
  const features          = useMemo(() => result?.features ?? [],     [result]);
  const derived           = useMemo(() => computeDerived(extractions),      [extractions]);
  const supplementary     = useMemo(() => computeSupplementary(extractions), [extractions]);
  const isStreaming        = result === null && sections.length > 0;

  const sortedSections = useMemo(() =>
    [...sections].sort((a, b) => {
      const ai = SECTION_ORDER.indexOf(a.section_id);
      const bi = SECTION_ORDER.indexOf(b.section_id);
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
    }),
  [sections]);

  const workflow = activeWorkflow(progress, failed);

  return (
    <main className="min-h-screen bg-[#08090b] text-[#e2e8f0]">

      {/* ── Top bar ── */}
      <ReportTopBar
        company={result?.company ?? null}
        modelOutput={result?.model_output ?? null}
        progress={progress}
        failed={failed}
        isComplete={result !== null}
      />

      {/* ── Processing banner ── */}
      {result === null && (
        <ProcessingBanner
          workflow={workflow}
          progress={progress}
          failed={failed}
          failedMessage={status?.error ?? null}
          lastMessage={messages[messages.length - 1] ?? null}
        />
      )}

      {/* ── Error strip ── */}
      {error && (
        <div className="border-b border-[#ef4444]/20 bg-[#ef4444]/[0.06] px-6 py-3 text-xs text-[#fca5a5]">
          {error}
        </div>
      )}

      {/* ── Main content ── */}
      <div className="mx-auto max-w-[1640px] px-5 py-6 lg:px-8">
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">

          {/* ── Left: financial content ── */}
          <div className="divide-y divide-white/[0.06] border border-white/[0.07] bg-[#0c0f14]">
            <FinancialSummaryBlock
              extractions={extractions}
              derived={derived}
              features={features}
              reportingContext={result?.reporting_context}
              onOpenStatements={() => setShowStatements(true)}
            />
            <AnalystMemoBlock sections={sortedSections} isStreaming={isStreaming} />
            <RatioAppendixBlock features={features} supplementary={supplementary} />
          </div>

          {/* ── Right: sidebar ── */}
          <aside className="divide-y divide-white/[0.07] border border-white/[0.07] bg-[#0c0f14] xl:sticky xl:top-[49px] xl:max-h-[calc(100vh-58px)] xl:overflow-y-auto">
            <ModelVerdictPanel
              modelOutput={result?.model_output ?? null}
              decision={result?.decision ?? null}
            />
            <AuditGovernancePanel extractions={extractions} />
            <ValidationPanel issues={result?.validation_issues ?? []} />
          </aside>

        </div>
      </div>

      {showStatements ? (
        <StatementsModal
          extractions={extractions}
          derived={derived}
          features={features}
          reportingContext={result?.reporting_context}
          onClose={() => setShowStatements(false)}
        />
      ) : null}
    </main>
  );
}

// ─── Top bar ─────────────────────────────────────────────────────────────────

function ReportTopBar({
  company, modelOutput, progress, failed, isComplete,
}: {
  company: ReportJobResult["company"] | null;
  modelOutput: ReportJobResult["model_output"] | null;
  progress: number;
  failed: boolean;
  isComplete: boolean;
}) {
  const score  = modelOutput?.engine_score_0_100 ?? null;
  const bucket = modelOutput?.decision_bucket ?? null;
  const meta   = bucket ? BUCKET_META[bucket] : null;

  return (
    <div className="sticky top-0 z-30 border-b border-white/[0.07] bg-[#08090b]/96 backdrop-blur-sm">
      <div className="mx-auto flex max-w-[1640px] items-center justify-between gap-6 px-5 py-3 lg:px-8">
        <div className="flex items-center gap-4 min-w-0">
          <Link
            className="shrink-0 text-[0.65rem] font-medium uppercase tracking-[0.22em] text-[#475569] transition hover:text-[#94a3b8]"
            href="/fulcrum/report/new"
          >
            ← New
          </Link>
          <span className="h-3 w-px bg-white/[0.08]" />
          {company?.company_name ? (
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-white">{company.company_name}</p>
              <p className="font-mono text-[0.62rem] text-[#475569]">
                {[company.cin, company.financial_year ? `FY${company.financial_year}` : null, company.sector, company.basis_preference]
                  .filter(Boolean).join(" · ")}
              </p>
            </div>
          ) : (
            <p className="text-[0.72rem] text-[#64748b]">Annual report analysis</p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-5">
          {isComplete && score !== null ? (
            <>
              <div className="text-right">
                <p className={`font-mono text-xl font-bold tabular-nums ${SCORE_COLOR(score)}`}>{score.toFixed(1)}</p>
                <p className="text-[0.58rem] uppercase tracking-[0.2em] text-[#475569]">risk score</p>
              </div>
              {meta && (
                <div className="text-right">
                  <p className={`text-[0.72rem] font-semibold ${meta.color}`}>{meta.label}</p>
                  <p className="text-[0.58rem] uppercase tracking-[0.2em] text-[#475569]">decision</p>
                </div>
              )}
            </>
          ) : !failed ? (
            <p className="font-mono text-sm text-[#475569]">{progress}%</p>
          ) : (
            <p className="text-xs text-[#ef4444]">Failed</p>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Processing banner ────────────────────────────────────────────────────────

function ProcessingBanner({
  workflow, progress, failed, failedMessage, lastMessage,
}: {
  workflow: { label: string; next: string };
  progress: number;
  failed: boolean;
  failedMessage: string | null;
  lastMessage: string | null;
}) {
  return (
    <div className={`border-b px-6 py-3 ${failed ? "border-[#ef4444]/20 bg-[#ef4444]/[0.05]" : "border-white/[0.05] bg-[#0a0c10]"}`}>
      <div className="mx-auto flex max-w-[1640px] items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          {!failed && (
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#8fb7ff]" />
          )}
          <span className={`text-xs ${failed ? "text-[#fca5a5]" : "text-[#94a3b8]"}`}>
            {failed ? (failedMessage ?? "Analysis failed") : workflow.label}
          </span>
          {lastMessage && !failed && (
            <span className="hidden text-[0.68rem] text-[#475569] md:block">{lastMessage}</span>
          )}
        </div>
        {!failed && (
          <div className="flex items-center gap-3">
            <div className="h-px w-36 overflow-hidden bg-white/[0.06]">
              <div
                className="h-full bg-[#8fb7ff]/50 transition-all duration-700"
                style={{ width: `${progress}%` }}
              />
            </div>
            <span className="font-mono text-[0.62rem] tabular-nums text-[#475569]">{progress}%</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Financial statements block ───────────────────────────────────────────────

function FinancialSummaryBlock({
  extractions, derived, features, reportingContext, onOpenStatements,
}: {
  extractions: ExtractedField[];
  derived: DerivedMetrics;
  features: FeatureValue[];
  reportingContext: ReportJobResult["reporting_context"] | undefined;
  onOpenStatements: () => void;
}) {
  const get = (f: string) => numericField(extractions, f);
  const raw = (f: string) => rawField(extractions, f);

  const revenue  = get("revenue");
  const ebitda   = get("ebitda");
  const pat      = get("pat");
  const assets   = get("total_assets");
  const borr     = get("total_borrowings");
  const equity   = get("total_equity");
  const cfo = get("cfo");
  const ncc = get("net_cash_change");

  const featVal = (name: string) => features.find((f) => f.feature === name)?.value ?? null;
  return (
    <div className="p-6 lg:p-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <SectionHeader label="Financial profile" sub={reportingContext?.normalized_monetary_unit ?? "INR crore"} />
          <p className="mt-3 max-w-3xl text-base leading-7 text-[#94a3b8]">
            This section summarizes the company&apos;s operating scale, funding profile, cash generation, and audit posture for the reported year.
          </p>
        </div>
        <button
          className="w-fit rounded-md border border-white/[0.12] bg-white/[0.03] px-4 py-2.5 text-sm font-medium text-[#e2e8f0] transition hover:bg-white/[0.06]"
          onClick={onOpenStatements}
          type="button"
        >
          View statements
        </button>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <SummaryMetric label="Revenue" value={fmtMoney(revenue)} note={fmtPct(featVal("ebitda_margin")) !== "—" ? `EBITDA margin ${fmtPct(featVal("ebitda_margin"))}` : undefined} />
        <SummaryMetric label="EBITDA" value={fmtMoney(ebitda)} note={derived.ebitdaInterestCoverage !== null ? `Coverage ${fmtX(derived.ebitdaInterestCoverage)}` : undefined} />
        <SummaryMetric label="PAT" value={fmtMoney(pat)} note={fmtPct(featVal("pat_margin")) !== "—" ? `PAT margin ${fmtPct(featVal("pat_margin"))}` : undefined} />
        <SummaryMetric label="Assets" value={fmtMoney(assets)} note={derived.assetTurnover !== null ? `Turnover ${fmtX(derived.assetTurnover)}` : undefined} />
        <SummaryMetric label="Borrowings" value={fmtMoney(borr)} note={featVal("debt_to_assets") !== null ? `Debt/assets ${fmtRatio(featVal("debt_to_assets"))}` : undefined} />
        <SummaryMetric label="Equity" value={fmtMoney(equity)} note={derived.debtToEquity !== null ? `Debt/equity ${fmtX(derived.debtToEquity)}` : undefined} />
        <SummaryMetric label="CFO" value={fmtMoney(cfo)} note={fmtRatio(featVal("cfo_to_ebitda")) !== "—" ? `CFO/EBITDA ${fmtRatio(featVal("cfo_to_ebitda"))}` : undefined} />
        <SummaryMetric label="Net cash change" value={fmtMoney(ncc)} note={derived.freeCashFlow !== null ? `FCF ${fmtMoney(derived.freeCashFlow)}` : undefined} />
        <SummaryMetric label="Audit opinion" value={String(raw("opinion_type") ?? "—")} note={String(raw("auditor_name") ?? "—")} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <StatTable heading="Cash flow and funding">
          <StatRow label="Cash from operations (CFO)" value={fmtMoney(cfo)} signal={cfo !== null && cfo < 0 ? "warn" : "ok"} />
          <StatRow label="Free cash flow" value={fmtMoney(derived.freeCashFlow)} signal={derived.freeCashFlow !== null && derived.freeCashFlow < 0 ? "warn" : "ok"} isDerived />
          <StatRow label="Net cash change" value={fmtMoney(ncc)} signal={ncc !== null && ncc < 0 ? "caution" : "ok"} />
          <StatRow label="Net debt" value={fmtMoney(derived.netDebt)} signal={derived.netDebt !== null && derived.netDebt > 0 ? "caution" : "ok"} isDerived />
        </StatTable>

        <StatTable heading="Structure and servicing">
          <StatRow label="Debt / equity" value={fmtX(derived.debtToEquity)} signal={derived.debtToEquity !== null && derived.debtToEquity > 3 ? "warn" : derived.debtToEquity !== null && derived.debtToEquity > 2 ? "caution" : "ok"} />
          <StatRow label="Debt / assets" value={fmtRatio(featVal("debt_to_assets"))} signal={featVal("debt_to_assets") !== null && featVal("debt_to_assets")! > 0.65 ? "warn" : featVal("debt_to_assets") !== null && featVal("debt_to_assets")! > 0.5 ? "caution" : "ok"} />
          <StatRow label="EBITDA / interest" value={fmtX(derived.ebitdaInterestCoverage)} signal={derived.ebitdaInterestCoverage !== null && derived.ebitdaInterestCoverage < 1.5 ? "warn" : derived.ebitdaInterestCoverage !== null && derived.ebitdaInterestCoverage < 2 ? "caution" : "ok"} />
          <StatRow label="CFO / EBITDA" value={fmtRatio(featVal("cfo_to_ebitda"))} signal={featVal("cfo_to_ebitda") !== null && featVal("cfo_to_ebitda")! < 0 ? "warn" : featVal("cfo_to_ebitda") !== null && featVal("cfo_to_ebitda")! < 0.8 ? "caution" : "ok"} />
        </StatTable>
      </div>

      {extractions.length === 0 && (
        <p className="mt-6 text-base text-[#475569]">Waiting for extraction data.</p>
      )}
    </div>
  );
}

// ─── Analyst memo block ───────────────────────────────────────────────────────

function AnalystMemoBlock({ sections, isStreaming }: { sections: ReportSection[]; isStreaming: boolean }) {
  return (
    <div className="p-6 lg:p-8">
      <SectionHeader label="Analyst memo" />
      {sections.length === 0 ? (
        <p className="mt-4 text-sm text-[#475569]">Waiting for generated sections.</p>
      ) : (
        <div className="mt-4 divide-y divide-white/[0.05]">
          {sections.map((section, i) => {
            const isLast = i === sections.length - 1;
            return (
              <article key={section.section_id} className="py-7 first:pt-0">
                <p className="mb-4 text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-[#475569]">
                  {section.title}
                </p>
                <div className="max-w-[78ch] space-y-4">
                  {memoBlocks(section.markdown).map((block, bi) => {
                    const bullet = block.match(/^(?:[*\-•]\s+)(.*)$/);
                    if (bullet) {
                      return (
                        <div
                          key={bi}
                          className="flex gap-4 rounded-md border border-white/[0.06] bg-white/[0.025] px-4 py-3"
                        >
                          <span className="mt-[0.72rem] h-2 w-2 shrink-0 rounded-full bg-[#d6d3cd]" />
                          <p className="text-[1.02rem] leading-8 text-[#d7dde7]">{bullet[1]}</p>
                        </div>
                      );
                    }
                    return <p key={bi} className="text-[1.02rem] leading-8 text-[#cbd5e1]">{block}</p>;
                  })}
                  {isStreaming && isLast && (
                    <div className="mt-2 h-3 w-40 animate-pulse rounded bg-white/[0.05]" />
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Ratio appendix block ─────────────────────────────────────────────────────

function RatioAppendixBlock({
  features, supplementary,
}: {
  features: FeatureValue[];
  supplementary: SupplementaryRatio[];
}) {
  const modelFeatures = features.filter((f) => !["log_total_assets", "log_revenue"].includes(f.feature));
  const scaleFeatures = features.filter((f) =>  ["log_total_assets", "log_revenue"].includes(f.feature));

  return (
    <div className="p-6 lg:p-8">
      <SectionHeader label="Ratio analysis" sub="core indicators and supporting measures" />
      <div className="mt-5 overflow-hidden rounded border border-white/[0.07]">
        <table className="w-full border-collapse">
          <thead className="bg-white/[0.02]">
            <tr className="border-b border-white/[0.07]">
              {["Metric", "Value", "Direction", "Benchmark"].map((h, i) => (
                <th
                  key={h}
                  className={`px-4 py-3 text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[#64748b] ${i === 0 ? "text-left" : i < 3 ? "text-right" : "text-left"}`}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.04]">
            {modelFeatures.map((f) => {
              const meta = FEATURE_LABELS[f.feature];
              const signal = featureSignal(f);
              const valStr = f.display_value ?? (typeof f.value === "number" ? f.value.toFixed(4) : "—");
              return (
                <tr key={f.feature} className={SIG_ROW[signal]}>
                  <td className="px-4 py-3 text-[0.95rem] font-medium text-[#cbd5e1]">{meta?.label ?? f.feature}</td>
                  <td className={`px-4 py-3 text-right font-mono text-[0.95rem] tabular-nums ${SIG_VAL[signal]}`}>{valStr}</td>
                  <td className="px-4 py-3 text-right font-mono text-[0.74rem] text-[#64748b]">{meta?.direction ?? "—"}</td>
                  <td className="px-4 py-3 text-[0.82rem] leading-6 text-[#94a3b8]">{meta?.bench ?? "—"}</td>
                </tr>
              );
            })}
            {supplementary.map((r) => (
              <tr key={r.feature} className={SIG_ROW[r.signal]}>
                <td className="px-4 py-3 text-[0.95rem] font-medium text-[#cbd5e1]">{r.label}</td>
                <td className={`px-4 py-3 text-right font-mono text-[0.95rem] tabular-nums ${SIG_VAL[r.signal]}`}>{r.fmt}</td>
                <td className="px-4 py-3 text-right font-mono text-[0.74rem] text-[#64748b]">—</td>
                <td className="px-4 py-3 text-[0.82rem] leading-6 text-[#94a3b8]">{r.bench}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {scaleFeatures.length > 0 ? (
        <div className="mt-4 rounded border border-white/[0.05] bg-white/[0.02] px-4 py-3">
          <p className="text-[0.72rem] uppercase tracking-[0.2em] text-[#475569]">Model context</p>
          <div className="mt-2 flex flex-wrap gap-4">
            {scaleFeatures.map((f) => (
              <div key={f.feature} className="font-mono text-sm text-[#64748b]">
                {FEATURE_LABELS[f.feature]?.label ?? f.feature}: {typeof f.value === "number" ? f.value.toFixed(4) : "—"}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {features.length === 0 && (
        <p className="mt-4 text-base text-[#475569]">Waiting for ratio data.</p>
      )}
    </div>
  );
}

// ─── Model verdict panel ──────────────────────────────────────────────────────

function ModelVerdictPanel({
  modelOutput, decision,
}: {
  modelOutput: ReportJobResult["model_output"] | null;
  decision: ReportJobResult["decision"] | null;
}) {
  const bucket = modelOutput?.decision_bucket ?? null;
  const meta   = bucket ? BUCKET_META[bucket] : null;
  const score  = modelOutput?.engine_score_0_100 ?? null;

  return (
    <div className="p-5">
      <SectionHeader label="Risk assessment" />

      {modelOutput ? (
        <div className="mt-4 space-y-5">
          {/* Score block */}
          <div className="flex items-end justify-between gap-4 border-b border-white/[0.06] pb-4">
            <div>
              <p className="text-[0.6rem] uppercase tracking-[0.22em] text-[#475569]">Engine score</p>
              <p className={`mt-1 font-mono text-4xl font-bold tabular-nums ${score !== null ? SCORE_COLOR(score) : "text-white"}`}>
                {score?.toFixed(1) ?? "—"}
              </p>
            </div>
            <div className="text-right">
              <p className="text-[0.6rem] uppercase tracking-[0.22em] text-[#475569]">Decision</p>
              <p className={`mt-1 text-base font-semibold ${meta?.color ?? "text-white"}`}>{meta?.label ?? "—"}</p>
            </div>
          </div>

          {/* Secondary scores */}
          <DataRow label="Audit score"    value={modelOutput.audit_score_0_100.toFixed(1)} />
          <DataRow label="Alignment"      value={modelOutput.model_alignment}
            valueClass={modelOutput.model_alignment === "disagree" ? "text-[#f59e0b]" : "text-[#94a3b8]"} />
          <DataRow label="Risk band"      value={modelOutput.engine_risk_band}
            valueClass={modelOutput.engine_risk_band === "HIGH" ? "text-[#ef4444]" : modelOutput.engine_risk_band === "MEDIUM" ? "text-[#f59e0b]" : "text-[#60a5fa]"} />
          <DataRow label="Probability"    value={(modelOutput.engine_probability * 100).toFixed(1) + "%"} />

          {/* Top drivers */}
          {modelOutput.top_drivers.length > 0 && (
            <div className="border-t border-white/[0.06] pt-4">
              <p className="mb-3 text-[0.6rem] font-semibold uppercase tracking-[0.26em] text-[#475569]">Key drivers</p>
              <ol className="space-y-2">
                {modelOutput.top_drivers.map((d, i) => (
                  <li key={i} className="flex gap-2.5">
                    <span className="mt-[0.1rem] shrink-0 font-mono text-[0.62rem] text-[#334155]">{String(i + 1).padStart(2, "0")}</span>
                    <span className="text-[0.9rem] leading-6 text-[#94a3b8]">{d}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {/* Final statement */}
          {decision?.final_statement && (
            <div className="border-t border-white/[0.06] pt-4">
              <p className="mb-2 text-[0.6rem] font-semibold uppercase tracking-[0.26em] text-[#475569]">Assessment summary</p>
              <p className="text-[0.95rem] leading-7 text-[#94a3b8]">{decision.final_statement}</p>
            </div>
          )}
          {decision?.confidence_statement && (
            <p className="text-[0.72rem] leading-5 text-[#475569]">{decision.confidence_statement}</p>
          )}
          {(decision?.warnings ?? []).map((w, i) => (
            <p key={i} className="text-[0.72rem] text-[#f59e0b]">{w}</p>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-[#475569]">Waiting for model output.</p>
      )}
    </div>
  );
}

// ─── Audit & governance panel ─────────────────────────────────────────────────

function AuditGovernancePanel({ extractions }: { extractions: ExtractedField[] }) {
  const raw = (f: string) => rawField(extractions, f);

  const auditFields = [
    { label: "Auditor",             value: String(raw("auditor_name") ?? "—"),   signal: "ok" as RiskSignal },
    { label: "Opinion",             value: String(raw("opinion_type") ?? "—"),   signal: "ok" as RiskSignal },
    { label: "Emphasis of matter",  value: raw("emphasis_of_matter")  ? "Yes" : "No", signal: (raw("emphasis_of_matter")  ? "caution" : "ok") as RiskSignal },
    { label: "Going concern",       value: raw("going_concern_uncertainty") ? "Yes" : "No", signal: (raw("going_concern_uncertainty") ? "warn" : "ok") as RiskSignal },
    { label: "Fraud reported",      value: raw("fraud_reported")   ? "Yes" : "No", signal: (raw("fraud_reported")   ? "warn" : "ok") as RiskSignal },
    { label: "Promoter holding",    value: numericField(extractions, "promoter_holding_pct") !== null ? `${numericField(extractions, "promoter_holding_pct")}%` : "—", signal: "ok" as RiskSignal },
  ];

  if (extractions.length === 0) return null;

  return (
    <div className="p-5">
      <SectionHeader label="Audit & governance" />
      <div className="mt-4 divide-y divide-white/[0.05]">
        {auditFields.map((row) => (
          <div key={row.label} className="flex items-center justify-between gap-3 py-2">
            <span className="text-[0.72rem] text-[#64748b]">{row.label}</span>
            <span className={`text-right text-[0.9rem] font-medium ${SIG_VAL[row.signal]}`}>{row.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Validation panel ─────────────────────────────────────────────────────────

function ValidationPanel({ issues }: { issues: ReportJobResult["validation_issues"] }) {
  if (!issues || issues.length === 0) return (
    <div className="p-5">
      <SectionHeader label="Report caveats" />
      <p className="mt-4 text-[0.78rem] text-[#334155]">No issues flagged.</p>
    </div>
  );

  const critical = issues.filter((i) => i.severity === "critical" || i.severity === "error");
  const warnings = issues.filter((i) => i.severity === "warning");
  const info     = issues.filter((i) => i.severity === "info" || !["critical","error","warning"].includes(i.severity));

  return (
    <div className="p-5">
      <SectionHeader label="Report caveats" sub={`${issues.length} note${issues.length !== 1 ? "s" : ""}`} />
      <div className="mt-4 space-y-4">
        {critical.length > 0 && (
          <div>
            <p className="mb-2 text-[0.6rem] font-semibold uppercase tracking-[0.22em] text-[#ef4444]">
              Critical · {critical.length}
            </p>
            {critical.map((i, idx) => (
              <p key={idx} className="py-1 text-[0.85rem] leading-6 text-[#fca5a5]">
                {i.field ? <span className="font-mono text-[#ef4444]">{i.field}: </span> : null}
                {i.message}
              </p>
            ))}
          </div>
        )}
        {warnings.length > 0 && (
          <div>
            <p className="mb-2 text-[0.6rem] font-semibold uppercase tracking-[0.22em] text-[#f59e0b]">
              Warning · {warnings.length}
            </p>
            {warnings.map((i, idx) => (
              <p key={idx} className="py-1 text-[0.85rem] leading-6 text-[#fde68a]">
                {i.field ? <span className="font-mono text-[#f59e0b]">{i.field}: </span> : null}
                {i.message}
              </p>
            ))}
          </div>
        )}
        {info.length > 0 && (
          <div>
            <p className="mb-2 text-[0.6rem] font-semibold uppercase tracking-[0.22em] text-[#475569]">
              Info · {info.length}
            </p>
            {info.map((i, idx) => (
              <p key={idx} className="py-1 text-[0.85rem] leading-6 text-[#64748b]">
                {i.field ? <span className="font-mono">{i.field}: </span> : null}
                {i.message}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Shared primitives ────────────────────────────────────────────────────────

function SectionHeader({ label, sub }: { label: string; sub?: string }) {
  return (
    <div className="flex items-baseline gap-2">
      <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-[#475569]">{label}</p>
      {sub && <p className="text-[0.72rem] text-[#334155]">{sub}</p>}
    </div>
  );
}

function StatTable({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <div className="mt-6">
      <p className="mb-3 text-[0.62rem] font-semibold uppercase tracking-[0.24em] text-[#334155]">{heading}</p>
      <div className="overflow-hidden rounded border border-white/[0.06] bg-white/[0.02]">
        <table className="w-full border-collapse">
          <tbody className="divide-y divide-white/[0.04]">{children}</tbody>
        </table>
      </div>
    </div>
  );
}

function StatRow({
  label, value, aside, signal = "ok", isDerived = false, isDimmed = false,
}: {
  label: string;
  value: string;
  aside?: string;
  signal?: RiskSignal;
  isDerived?: boolean;
  isDimmed?: boolean;
}) {
  return (
    <tr className={`${SIG_ROW[signal]}`}>
      <td className={`px-4 py-3 text-[0.9rem] ${isDerived ? "italic text-[#64748b]" : isDimmed ? "text-[#64748b]" : "text-[#94a3b8]"}`}>
        {label}
      </td>
      <td className="px-4 py-3 text-right">
        <span className={`font-mono text-[0.92rem] tabular-nums ${SIG_VAL[signal]}`}>{value}</span>
        {aside && <span className="ml-3 font-mono text-[0.74rem] text-[#475569]">{aside}</span>}
      </td>
    </tr>
  );
}

function DataRow({ label, value, valueClass }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-[0.72rem] text-[#64748b]">{label}</span>
      <span className={`font-mono text-[0.8rem] ${valueClass ?? "text-[#94a3b8]"}`}>{value}</span>
    </div>
  );
}

function SummaryMetric({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded border border-white/[0.07] bg-white/[0.02] p-4">
      <p className="text-[0.72rem] uppercase tracking-[0.2em] text-[#64748b]">{label}</p>
      <p className="mt-2 font-mono text-xl font-semibold text-white">{value}</p>
      {note ? <p className="mt-2 text-sm leading-6 text-[#94a3b8]">{note}</p> : null}
    </div>
  );
}

function StatementsModal({
  extractions,
  derived,
  features,
  reportingContext,
  onClose,
}: {
  extractions: ExtractedField[];
  derived: DerivedMetrics;
  features: FeatureValue[];
  reportingContext: ReportJobResult["reporting_context"] | undefined;
  onClose: () => void;
}) {
  const get = (f: string) => numericField(extractions, f);
  const featVal = (name: string) => features.find((f) => f.feature === name)?.value ?? null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/80 p-5 backdrop-blur-sm">
      <div className="max-h-[92vh] w-full max-w-[1220px] overflow-y-auto rounded-lg border border-white/[0.08] bg-[#0c0f14] shadow-2xl shadow-black/70">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-white/[0.07] bg-[#0e1117]/96 px-7 py-5 backdrop-blur-sm">
          <div>
            <p className="text-[0.7rem] font-semibold uppercase tracking-[0.28em] text-[#475569]">Financial statements</p>
            <p className="mt-1 text-sm leading-6 text-[#64748b]">
              Raw income statement and balance sheet view · {reportingContext?.normalized_monetary_unit ?? "INR crore"}
            </p>
          </div>
          <button
            className="rounded-md border border-white/[0.12] px-4 py-2.5 text-sm font-medium text-[#e2e8f0] transition hover:bg-white/[0.06]"
            onClick={onClose}
            type="button"
          >
            Close
          </button>
        </div>

        <div className="space-y-8 p-7 lg:p-9">
          <StatTable heading="Income statement">
            <StatRow label="Revenue" value={fmtMoney(get("revenue"))} signal="ok" />
            <StatRow label="EBITDA" value={fmtMoney(get("ebitda"))} aside={fmtPct(featVal("ebitda_margin"))} signal={get("ebitda") !== null && get("ebitda")! < 0 ? "warn" : "ok"} />
            <StatRow label="Depreciation" value={fmtMoney(get("depreciation"))} signal="ok" isDimmed />
            <StatRow label="EBIT" value={fmtMoney(derived.ebit)} signal={derived.ebit !== null && derived.ebit < 0 ? "warn" : "ok"} isDerived />
            <StatRow label="Interest expense" value={fmtMoney(get("interest_expense"))} aside={fmtPct(derived.interestToRevenue)} signal={derived.interestToRevenue !== null && derived.interestToRevenue > 0.15 ? "warn" : "ok"} />
            <StatRow label="EBT" value={fmtMoney(derived.ebt)} signal={derived.ebt !== null && derived.ebt < 0 ? "warn" : "ok"} isDerived />
            <StatRow label="Tax expense" value={fmtMoney(get("tax_expense"))} aside={derived.effectiveTaxRate !== null ? `${(derived.effectiveTaxRate * 100).toFixed(1)}% ETR` : undefined} signal="ok" isDimmed />
            <StatRow label="PAT" value={fmtMoney(get("pat"))} aside={fmtPct(featVal("pat_margin"))} signal={get("pat") !== null && get("pat")! < 0 ? "warn" : "ok"} />
          </StatTable>

          <StatTable heading="Balance sheet">
            <StatRow label="Total assets" value={fmtMoney(get("total_assets"))} signal="ok" />
            <StatRow label="Current assets" value={fmtMoney(get("current_assets"))} signal="ok" isDimmed />
            <StatRow label="Cash & equivalents" value={fmtMoney(get("cash_and_equivalents"))} signal={get("cash_and_equivalents") !== null && get("cash_and_equivalents")! < 50 ? "caution" : "ok"} isDimmed />
            <StatRow label="Receivables" value={fmtMoney(get("receivables"))} signal="ok" isDimmed />
            <StatRow label="Inventory" value={fmtMoney(get("inventory"))} signal="ok" isDimmed />
            <StatRow label="Current liabilities" value={fmtMoney(get("current_liabilities"))} signal="ok" />
            <StatRow label="Working capital" value={fmtMoney(derived.workingCapital)} signal={derived.workingCapital !== null && derived.workingCapital < 0 ? "warn" : "ok"} isDerived />
            <StatRow label="Total borrowings" value={fmtMoney(get("total_borrowings"))} signal={derived.debtToAssets !== null && derived.debtToAssets > 0.65 ? "warn" : derived.debtToAssets !== null && derived.debtToAssets > 0.5 ? "caution" : "ok"} />
            <StatRow label="Net debt" value={fmtMoney(derived.netDebt)} signal={derived.netDebt !== null && derived.netDebt > 0 ? "caution" : "ok"} isDerived />
            <StatRow label="Total equity" value={fmtMoney(get("total_equity"))} signal={get("total_equity") !== null && get("total_equity")! < 0 ? "warn" : "ok"} />
            <StatRow label="Retained earnings" value={fmtMoney(get("retained_earnings"))} signal={get("retained_earnings") !== null && get("retained_earnings")! < 0 ? "warn" : "ok"} isDimmed />
            <StatRow label="Contingent liabilities" value={fmtMoney(get("contingent_liabilities_amount"))} signal={get("contingent_liabilities_amount") !== null && get("contingent_liabilities_amount")! > 0 ? "caution" : "ok"} />
          </StatTable>

        </div>
      </div>
    </div>
  );
}
