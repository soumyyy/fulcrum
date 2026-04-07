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

const PIPELINE_STAGES = [
  { label: "Uploading annual report", threshold: 0 },
  { label: "Parsing document", threshold: 15 },
  { label: "Extracting fields", threshold: 35 },
  { label: "Validating values", threshold: 55 },
  { label: "Calculating ratios", threshold: 70 },
  { label: "Running models", threshold: 82 },
  { label: "Generating report", threshold: 92 },
  { label: "Ready for review", threshold: 100 },
];

type RatioStandard = {
  label: string;
  standard: string;
  interpretation: string;
  analystRead: string;
  source: string;
};

const MONETARY_FIELDS = new Set([
  "revenue",
  "pat",
  "interest_expense",
  "tax_expense",
  "depreciation",
  "ebitda",
  "total_equity",
  "total_borrowings",
  "total_assets",
  "retained_earnings",
  "cfo",
  "cfi",
  "cff",
  "net_cash_change",
  "current_assets",
  "current_liabilities",
  "cash_and_equivalents",
  "inventory",
  "receivables",
  "capex",
  "contingent_liabilities_amount",
]);

const FEATURE_STANDARDS: Record<string, RatioStandard> = {
  debt_to_assets: {
    label: "Debt / Assets",
    standard: "External benchmark: above 1.0 means debt exceeds assets. Internal caution line: above 0.50 means debt funds most assets and should be peer-checked.",
    interpretation: "Higher values increase balance-sheet leverage risk.",
    analystRead: "Use this as the first solvency lens. Low debt/assets does not eliminate default risk, but high values reduce refinancing flexibility and increase sensitivity to asset impairments.",
    source: "Debt-ratio guidance; sector context required.",
  },
  ebitda_margin: {
    label: "EBITDA Margin",
    standard: "No universal threshold. Compare against sector peers; positive and expanding margins are stronger.",
    interpretation: "Lower or compressing values indicate weaker operating profitability.",
    analystRead: "This is the operating-profit buffer before interest, taxes, depreciation, and amortization. A weak margin makes leverage and liquidity problems harder to absorb.",
    source: "Margin benchmarks vary by industry.",
  },
  pat_margin: {
    label: "PAT Margin",
    standard: "No universal threshold. Positive margins are required for self-funded balance-sheet repair.",
    interpretation: "Negative or thin margins reduce default buffer.",
    analystRead: "This indicates how much final profit is retained from revenue after all charges. Thin PAT margins can make cash-flow volatility more dangerous.",
    source: "Profitability benchmark; sector context required.",
  },
  roa: {
    label: "ROA",
    standard: "Rule of thumb: around 5% is often treated as acceptable and 20%+ as very strong, but industry matters.",
    interpretation: "Lower ROA suggests weak asset productivity.",
    analystRead: "This tests whether the asset base is producing adequate earnings. A company can be large and still risky if assets are not generating returns.",
    source: "ROA benchmark guidance; industry context required.",
  },
  retained_earnings_to_assets: {
    label: "Retained Earnings / Assets",
    standard: "Positive is stronger. Negative accumulated earnings are a structural warning sign.",
    interpretation: "Lower values indicate weaker internally accumulated capital cushion.",
    analystRead: "This is a rough accumulated-profit cushion. Weak or negative retained earnings means the company has less internally built capital to absorb stress.",
    source: "Balance-sheet cushion heuristic.",
  },
  cfo_to_assets: {
    label: "CFO / Assets",
    standard: "Positive is the first hurdle. Higher values imply better cash generation from the asset base.",
    interpretation: "Negative values suggest cash-flow stress even if accounting profit is positive.",
    analystRead: "This links operating cash generation to the scale of assets deployed. Low values can indicate that asset-heavy growth is not converting into cash.",
    source: "Cash-generation heuristic.",
  },
  cfo_to_ebitda: {
    label: "CFO / EBITDA",
    standard: "Internal convention: near 1.0 implies strong cash conversion; materially below 1.0 needs review.",
    interpretation: "Lower values can point to working-capital strain or low earnings quality.",
    analystRead: "This is one of the most important earnings-quality checks. If EBITDA is strong but CFO is weak, the analyst should inspect receivables, inventory, advances, and cash-flow notes.",
    source: "Internal cash-conversion convention.",
  },
  net_cash_change_to_assets: {
    label: "Net Cash Change / Assets",
    standard: "Contextual. Positive is preferable; persistent negative values require liquidity review.",
    interpretation: "Negative values can indicate net cash burn.",
    analystRead: "This is not a standalone default signal, but it shows whether cash is accumulating or being consumed relative to balance-sheet size.",
    source: "Liquidity movement heuristic.",
  },
  log_total_assets: {
    label: "Scale: Total Assets",
    standard: "Contextual scale control used by the model, not a standalone risk threshold.",
    interpretation: "Used to normalize firm size effects.",
    analystRead: "Scale changes how ratios should be interpreted; it is a model control, not a risk conclusion.",
    source: "Model control variable.",
  },
  log_revenue: {
    label: "Scale: Revenue",
    standard: "Contextual scale control used by the model, not a standalone risk threshold.",
    interpretation: "Used to normalize firm size effects.",
    analystRead: "Revenue scale helps the model compare companies more fairly, but it should not be read as good or bad by itself.",
    source: "Model control variable.",
  },
};

const SUPPLEMENTARY_STANDARDS: Record<string, RatioStandard> = {
  current_ratio: {
    label: "Current Ratio",
    standard: "Common benchmark: roughly 1.5-3.0 is often considered healthy; below 1.0 can indicate near-term liquidity pressure.",
    interpretation: "Shows whether current assets cover current liabilities.",
    analystRead: "Use this as the broad liquidity test. A healthy value still needs quality checks because receivables or inventory may not convert to cash quickly.",
    source: "Current-ratio benchmark guidance.",
  },
  cash_ratio: {
    label: "Cash Ratio",
    standard: "Common benchmark: 0.5-1.0 is often acceptable by sector; 1.0 means cash and equivalents cover current liabilities; below 0.5 can be risky.",
    interpretation: "Stricter liquidity test than current ratio.",
    analystRead: "This strips out inventory and receivables. A weak cash ratio is not automatically fatal, but it raises dependence on collections, refinancing, or working-capital facilities.",
    source: "Cash-ratio benchmark guidance.",
  },
  working_capital_to_assets: {
    label: "Working Capital / Assets",
    standard: "Positive is generally preferable. Negative values mean short-term obligations exceed short-term assets.",
    interpretation: "Captures short-term balance-sheet buffer relative to asset base.",
    analystRead: "This puts net working capital in balance-sheet context. Negative values deserve review unless the business model naturally runs on supplier credit.",
    source: "Liquidity buffer heuristic.",
  },
  contingent_liabilities_to_assets: {
    label: "Contingent Liabilities / Assets",
    standard: "No universal threshold. Large contingent exposure relative to assets needs legal/audit review.",
    interpretation: "Highlights off-balance-sheet or disputed exposures that may crystallize.",
    analystRead: "This is a tail-risk lens. Even if not recognized as debt today, material claims can worsen liquidity or solvency if they crystallize.",
    source: "Risk-review heuristic.",
  },
  ebitda_to_interest: {
    label: "EBITDA / Interest",
    standard: "Common benchmark: 2.0 or higher is often treated as more comfortable; below 1.5 is weak.",
    interpretation: "Measures ability of operating earnings to cover interest burden.",
    analystRead: "This is the core debt-service coverage check. Strong coverage can offset moderate leverage; weak coverage makes refinancing and covenant risk more acute.",
    source: "Interest-coverage benchmark guidance.",
  },
};

function markdownLite(value: string) {
  return value.replaceAll("**", "");
}

function memoBlocks(value: string) {
  return markdownLite(value)
    .split(/\n+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function upsertSection(current: ReportSection[], next: ReportSection) {
  const index = current.findIndex((section) => section.section_id === next.section_id);
  if (index === -1) return [...current, next];
  const copy = [...current];
  copy[index] = next;
  return copy;
}

function activeWorkflow(progress: number, failed: boolean) {
  if (failed) return { label: "Analysis failed", next: "Review backend error" };
  const current = [...PIPELINE_STAGES].reverse().find((stage) => progress >= stage.threshold) ?? PIPELINE_STAGES[0];
  const next = PIPELINE_STAGES.find((stage) => stage.threshold > progress);
  return { label: current.label, next: next?.label ?? "Analyst review" };
}

function displayField(extractions: ExtractedField[], field: string) {
  const item = extractions.find((entry) => entry.field === field);
  if (!item) return "--";
  const value = item.normalized_value ?? item.value;
  if (value === null || value === undefined || value === "") return "--";
  if (typeof value === "number") {
    const unit = MONETARY_FIELDS.has(field) && item.normalized_value !== null && item.normalized_value !== undefined ? "INR crore" : item.unit;
    return `${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}${unit ? ` ${unit}` : ""}`;
  }
  return String(value);
}

function numericField(extractions: ExtractedField[], field: string) {
  const item = extractions.find((entry) => entry.field === field);
  const value = item?.normalized_value ?? item?.value;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value.replaceAll(",", ""));
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function safeRatio(numerator: number | null, denominator: number | null) {
  if (numerator === null || denominator === null || denominator === 0) return null;
  return numerator / denominator;
}

function supplementaryRatios(extractions: ExtractedField[]) {
  const currentAssets = numericField(extractions, "current_assets");
  const currentLiabilities = numericField(extractions, "current_liabilities");
  const cash = numericField(extractions, "cash_and_equivalents");
  const totalAssets = numericField(extractions, "total_assets");
  const contingentLiabilities = numericField(extractions, "contingent_liabilities_amount");
  const ebitda = numericField(extractions, "ebitda");
  const interest = numericField(extractions, "interest_expense");

  return [
    { feature: "current_ratio", value: safeRatio(currentAssets, currentLiabilities) },
    { feature: "cash_ratio", value: safeRatio(cash, currentLiabilities) },
    {
      feature: "working_capital_to_assets",
      value: currentAssets === null || currentLiabilities === null ? null : safeRatio(currentAssets - currentLiabilities, totalAssets),
    },
    { feature: "contingent_liabilities_to_assets", value: safeRatio(contingentLiabilities, totalAssets) },
    { feature: "ebitda_to_interest", value: safeRatio(ebitda, interest) },
  ].filter((item) => item.value !== null);
}

function formatFeatureValue(feature: FeatureValue) {
  if (feature.display_value) return feature.display_value;
  if (typeof feature.value === "number") return feature.value.toFixed(4);
  return "--";
}

function featureTone(feature: FeatureValue) {
  if (typeof feature.value !== "number") return "border-white/10 bg-white/[0.035]";
  if (feature.feature === "debt_to_assets" && feature.value > 0.5) return "border-[#ff6b35]/45 bg-[#ff6b35]/10";
  if (["ebitda_margin", "pat_margin", "roa", "cfo_to_assets", "cfo_to_ebitda"].includes(feature.feature) && feature.value < 0) {
    return "border-[#ff6b35]/45 bg-[#ff6b35]/10";
  }
  return "border-white/10 bg-black/25";
}

function ratioTone(feature: string, value: number | null) {
  if (value === null) return "border-white/10 bg-white/[0.035]";
  if (feature === "current_ratio" && value < 1) return "border-[#ff6b35]/45 bg-[#ff6b35]/10";
  if (feature === "cash_ratio" && value < 0.5) return "border-[#ff6b35]/45 bg-[#ff6b35]/10";
  if (feature === "working_capital_to_assets" && value < 0) return "border-[#ff6b35]/45 bg-[#ff6b35]/10";
  if (feature === "ebitda_to_interest" && value < 1.5) return "border-[#ff6b35]/45 bg-[#ff6b35]/10";
  if (feature === "contingent_liabilities_to_assets" && value > 0.1) return "border-[#ff6b35]/45 bg-[#ff6b35]/10";
  return "border-white/10 bg-black/25";
}

export function ReportRunWorkspace({ jobId }: { jobId: string }) {
  const [status, setStatus] = useState<ReportStatusResponse | null>(null);
  const [result, setResult] = useState<ReportJobResult | null>(null);
  const [sections, setSections] = useState<ReportSection[]>([]);
  const [messages, setMessages] = useState<string[]>([]);
  const [showNotes, setShowNotes] = useState(false);
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
      setMessages((current) => [...current.slice(-9), message]);
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

  const workflow = activeWorkflow(progress, failed);
  const title = result?.company.company_name ?? "Annual report analysis";
  const finalStatement = result?.decision?.final_statement;
  const modelOutput = result?.model_output ?? null;
  const featureRows = useMemo(() => result?.features ?? [], [result]);
  const extractions = useMemo(() => result?.extractions ?? [], [result]);
  const supplementaryRows = useMemo(() => supplementaryRatios(extractions), [extractions]);

  return (
    <main className="min-h-screen bg-[#08090b] text-[#f7f0df]">
      <div className="pointer-events-none fixed inset-0 [background:radial-gradient(circle_at_16%_12%,rgba(255,107,53,0.18),transparent_26%),radial-gradient(circle_at_82%_14%,rgba(245,230,200,0.12),transparent_22%),linear-gradient(110deg,rgba(255,255,255,0.035)_1px,transparent_1px)] [background-size:auto,auto,48px_48px]" />
      <section className="relative mx-auto flex min-h-screen w-full max-w-[1720px] flex-col gap-5 px-5 py-5 lg:px-7">
        <header className="rounded-[2rem] border border-white/10 bg-[#101216]/92 p-5 shadow-2xl shadow-black/45">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <Link className="text-xs uppercase tracking-[0.24em] text-[#ffb38f]" href="/fulcrum/report/new">← New report</Link>
              <p className="mt-6 text-[0.65rem] uppercase tracking-[0.32em] text-[#9ba1ad]">Expert risk report</p>
              <h1 className="mt-2 text-5xl font-semibold leading-[0.9] tracking-[-0.08em] text-white">{title}</h1>
              <p className="mt-3 max-w-4xl text-sm leading-6 text-[#cfc5b1]">
                {result ? `${result.company.financial_year ?? "FY"} · ${result.company.sector ?? "Sector pending"} · ${result.company.basis_preference}` : workflow.label}
              </p>
            </div>
            <div className="relative rounded-[1.5rem] border border-[#ff6b35]/35 bg-[#ff6b35]/10 p-4 text-right">
              <div className="flex items-center justify-end gap-2">
                <p className="text-[0.65rem] uppercase tracking-[0.24em] text-[#ffb38f]">{workflow.label}</p>
                <button
                  aria-label="Show live processing notes"
                  className="grid h-7 w-7 place-items-center rounded-full border border-[#ffb38f]/45 text-xs text-[#ffb38f]"
                  onClick={() => setShowNotes((value) => !value)}
                  type="button"
                >
                  i
                </button>
              </div>
              <p className="mt-1 font-mono text-5xl font-semibold text-white">{progress}%</p>
              <p className="mt-1 text-xs text-[#cfc5b1]">Next: {workflow.next}</p>
              {showNotes ? (
                <div className="absolute right-0 top-[calc(100%+0.75rem)] z-20 w-[min(28rem,90vw)] rounded-3xl border border-white/10 bg-[#121419] p-4 text-left shadow-2xl shadow-black/60">
                  <p className="text-[0.65rem] uppercase tracking-[0.24em] text-[#9ba1ad]">Live processing notes</p>
                  <div className="mt-3 space-y-2">
                    {messages.length ? messages.map((message, index) => <p className="text-xs leading-5 text-[#cfc5b1]" key={`${message}-${index}`}>{message}</p>) : <p className="text-xs text-[#9ba1ad]">No low-level notes yet.</p>}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
          <div className="mt-5 h-2 overflow-hidden rounded-full bg-white/10">
            <div className="h-full rounded-full bg-[#ff6b35] transition-all duration-500" style={{ width: `${Math.min(100, progress)}%` }} />
          </div>
        </header>

        {error ? <Notice title="Report error" message={error} /> : null}
        {status?.status === "failed" && status.error ? <Notice title="Analysis failed" message={status.error} /> : null}

        <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <section className="rounded-[2rem] border border-white/10 bg-[#0e1014]/95 shadow-2xl shadow-black/40">
            <CompanyOverview extractions={extractions} result={result} />
            <GeneratedSections sections={sections} />
            <RiskAppendix features={featureRows} modelOutput={modelOutput} supplementaryRatios={supplementaryRows} />
          </section>

          <aside className="space-y-5 xl:sticky xl:top-5">
            <ModelDecision finalStatement={finalStatement} modelOutput={modelOutput} />
            <FinancialSnapshot extractions={extractions} />
            <ValidationPanel result={result} />
          </aside>
        </div>
      </section>
    </main>
  );
}

function CompanyOverview({ extractions, result }: { extractions: ExtractedField[]; result: ReportJobResult | null }) {
  return (
    <section className="border-b border-white/10 p-6 lg:p-8">
      <p className="text-[0.65rem] uppercase tracking-[0.32em] text-[#9ba1ad]">Company profile</p>
      <div className="mt-4 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(420px,0.8fr)]">
        <div>
          <h2 className="text-4xl font-semibold tracking-[-0.07em] text-white">{result?.company.company_name ?? displayField(extractions, "company_name")}</h2>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-[#cfc5b1]">
            {result?.company.financial_year ?? displayField(extractions, "financial_year")} · {result?.company.sector ?? "Sector pending"} · {result?.company.basis_preference ?? "basis pending"}
          </p>
          <p className="mt-2 font-mono text-xs text-[#7f8794]">{result?.company.cin ?? displayField(extractions, "cin")}</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <CompactMetric label="Assets" value={displayField(extractions, "total_assets")} />
          <CompactMetric label="Borrowings" value={displayField(extractions, "total_borrowings")} />
          <CompactMetric label="Equity" value={displayField(extractions, "total_equity")} />
        </div>
      </div>
    </section>
  );
}

function RiskAppendix({
  features,
  modelOutput,
  supplementaryRatios,
}: {
  features: FeatureValue[];
  modelOutput: ReportJobResult["model_output"];
  supplementaryRatios: { feature: string; value: number | null }[];
}) {
  const rows = [
    ...features.map((feature) => {
      const standard = FEATURE_STANDARDS[feature.feature] ?? {
        label: feature.feature,
        standard: "Contextual model input.",
        interpretation: "Review with peers.",
        analystRead: "Use this as supporting model context, not as a standalone decision rule.",
        source: "Internal model feature.",
      };
      return {
        key: feature.feature,
        label: standard.label,
        value: formatFeatureValue(feature),
        standard,
        tone: featureTone(feature),
      };
    }),
    ...supplementaryRatios.map((ratio) => {
      const standard = SUPPLEMENTARY_STANDARDS[ratio.feature];
      return {
        key: ratio.feature,
        label: standard.label,
        value: ratio.value?.toFixed(4) ?? "--",
        standard,
        tone: ratioTone(ratio.feature, ratio.value),
      };
    }),
  ];

  return (
    <section className="border-t border-white/10 p-6 lg:p-8">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-[0.65rem] uppercase tracking-[0.32em] text-[#9ba1ad]">Appendix</p>
          <h2 className="mt-2 text-3xl font-semibold tracking-[-0.06em] text-white">Ratio evidence and standards</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[#aeb7c5]">Supporting ratio calculations used to read the memo. These are deliberately separated from the narrative so the report scans like a document.</p>
        </div>
        {modelOutput ? <CompactMetric label="Risk score" value={modelOutput.engine_score_0_100.toFixed(1)} /> : null}
      </div>

      <div className="mt-6 divide-y divide-white/10 rounded-[1.5rem] border border-white/10 bg-black/20">
        {rows.map((row) => (
          <article className={`grid gap-4 p-4 lg:grid-cols-[220px_90px_minmax(0,1fr)] ${row.tone}`} key={row.key}>
            <div>
              <h3 className="text-base font-semibold tracking-[-0.03em] text-white">{row.label}</h3>
              <p className="mt-1 text-[0.65rem] uppercase tracking-[0.18em] text-[#7f8794]">{row.standard.source}</p>
            </div>
            <p className="font-mono text-xl font-semibold text-[#ffb38f]">{row.value}</p>
            <div>
              <p className="text-sm leading-6 text-[#d8d2c3]">{row.standard.interpretation}</p>
              <p className="mt-2 text-xs leading-5 text-[#aeb7c5]">{row.standard.standard}</p>
              <p className="mt-2 text-xs leading-5 text-[#8f98a6]">{row.standard.analystRead}</p>
            </div>
          </article>
        ))}
        {!rows.length ? <p className="p-8 text-center text-[#9ba1ad]">Waiting for ratio evidence.</p> : null}
      </div>
    </section>
  );
}

function GeneratedSections({ sections }: { sections: ReportSection[] }) {
  return (
    <section className="p-6 lg:p-8">
      <p className="text-[0.65rem] uppercase tracking-[0.32em] text-[#9ba1ad]">Analyst memo</p>
      <div className="mt-4 divide-y divide-white/10">
        {sections.map((section) => (
          <article className="grid gap-5 py-7 lg:grid-cols-[260px_minmax(0,1fr)]" key={section.section_id}>
            <h3 className="text-2xl font-semibold leading-tight tracking-[-0.05em] text-white">{section.title}</h3>
            <div className="space-y-3">
              {memoBlocks(section.markdown).map((block, index) => {
                const bullet = block.match(/^(?:[*-]\s+)(.*)$/);
                if (bullet) {
                  return (
                    <div className="flex gap-3 text-sm leading-7 text-[#ded6c5]" key={`${section.section_id}-${index}`}>
                      <span className="mt-3 h-1.5 w-1.5 shrink-0 rounded-full bg-[#ffb38f]" />
                      <p>{bullet[1]}</p>
                    </div>
                  );
                }
                return <p className="text-sm leading-7 text-[#ded6c5]" key={`${section.section_id}-${index}`}>{block}</p>;
              })}
            </div>
          </article>
        ))}
        {!sections.length ? <div className="rounded-[1.5rem] border border-white/10 bg-black/20 p-8 text-center text-[#9ba1ad]">Waiting for generated sections.</div> : null}
      </div>
    </section>
  );
}

function ModelDecision({ finalStatement, modelOutput }: { finalStatement: string | undefined; modelOutput: ReportJobResult["model_output"] }) {
  return (
    <section className="rounded-[2rem] border border-[#ff6b35]/25 bg-[#ff6b35]/10 p-5 shadow-xl shadow-black/35">
      <p className="text-[0.65rem] uppercase tracking-[0.32em] text-[#ffb38f]">Decision</p>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <CompactMetric label="Bucket" value={modelOutput?.decision_bucket ?? "--"} />
        <CompactMetric label="Benchmark" value={modelOutput ? modelOutput.audit_score_0_100.toFixed(1) : "--"} />
      </div>
      <p className="mt-5 text-sm leading-7 text-[#f5e6c8]">{finalStatement ?? "Final model statement will appear when scoring completes."}</p>
    </section>
  );
}

function FinancialSnapshot({ extractions }: { extractions: ExtractedField[] }) {
  return (
    <section className="rounded-[2rem] border border-white/10 bg-[#101216]/92 p-5 shadow-xl shadow-black/35">
      <p className="text-[0.65rem] uppercase tracking-[0.32em] text-[#9ba1ad]">Financial snapshot</p>
      <div className="mt-5 grid gap-3">
        <CompactMetric label="Revenue" value={displayField(extractions, "revenue")} />
        <CompactMetric label="PAT" value={displayField(extractions, "pat")} />
        <CompactMetric label="EBITDA" value={displayField(extractions, "ebitda")} />
        <CompactMetric label="CFO" value={displayField(extractions, "cfo")} />
        <CompactMetric label="Net cash change" value={displayField(extractions, "net_cash_change")} />
        <CompactMetric label="Contingent liabilities" value={displayField(extractions, "contingent_liabilities_amount")} />
      </div>
    </section>
  );
}

function ValidationPanel({ result }: { result: ReportJobResult | null }) {
  return (
    <section className="rounded-[2rem] border border-white/10 bg-[#101216]/92 p-5 shadow-xl shadow-black/35">
      <p className="text-[0.65rem] uppercase tracking-[0.32em] text-[#9ba1ad]">Validation and caveats</p>
      <div className="mt-4 space-y-2">
        {(result?.validation_issues ?? []).map((issue) => <p className="rounded-2xl bg-white/[0.045] p-3 text-xs leading-5 text-[#d8d2c3]" key={issue.message}>{issue.message}</p>)}
        {!result?.validation_issues?.length ? <p className="text-sm text-[#9ba1ad]">Validation notes will appear after extraction.</p> : null}
      </div>
    </section>
  );
}

function CompactMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/20 p-3">
      <p className="text-[0.6rem] uppercase tracking-[0.22em] text-[#9ba1ad]">{label}</p>
      <p className="mt-1 break-words font-mono text-sm font-semibold text-white">{value}</p>
    </div>
  );
}

function Notice({ title, message }: { title: string; message: string }) {
  return (
    <div className="rounded-[1.5rem] border border-[#ff6b35]/40 bg-[#ff6b35]/10 p-5">
      <p className="text-sm font-semibold text-[#fff3d7]">{title}</p>
      <p className="mt-2 text-sm leading-6 text-[#ffd8c5]">{message}</p>
    </div>
  );
}
