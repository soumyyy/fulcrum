"use client";

import { useState, useTransition } from "react";

type YearScore = {
  financial_year: number;
  ml_probability: number;
  model_threshold: number;
  ml_class: string;
  risk_band: string;
  rule_flags_triggered: string[];
  rule_flag_count: number;
  top_reasons: string[];
  support_summary: string;
  framing_message: string;
  imputed_feature_fraction: number;
};

type ScoreResponse = {
  company_name: string;
  cin: string;
  years_received: number;
  latest_financial_year: number;
  model_name: string;
  model_version: string;
  training_dataset_sha256: string;
  feature_list_version: string;
  threshold_version: string;
  rule_set_version: string;
  ml_probability: number;
  model_threshold: number;
  ml_class: string;
  risk_band: string;
  rule_flags_triggered: string[];
  rule_flag_count: number;
  top_reasons: string[];
  support_summary: string;
  framing_message: string;
  yearwise_scores: YearScore[];
  warnings: string[];
};

function formatMetric(value: number, digits = 3) {
  if (!Number.isFinite(value)) {
    return "n/a";
  }
  return value.toFixed(digits);
}

function RiskBandPill({ band }: { band: string }) {
  const classes =
    band === "High"
      ? "border-rose-400/30 bg-rose-400/10 text-rose-100"
      : band === "Medium"
        ? "border-amber-300/30 bg-amber-300/10 text-amber-100"
        : "border-emerald-300/30 bg-emerald-300/10 text-emerald-100";

  return (
    <span
      className={`rounded-full border px-4 py-2 text-[0.68rem] font-semibold uppercase tracking-[0.18em] ${classes}`}
    >
      {band}
    </span>
  );
}

export function ScorePanel() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ScoreResponse | null>(null);
  const [isPending, startTransition] = useTransition();

  function submitScore() {
    if (!selectedFile) {
      setError("Select a CSV file before scoring.");
      return;
    }

    setError(null);

    startTransition(async () => {
      try {
        const formData = new FormData();
        formData.append("file", selectedFile);

        const response = await fetch("/api/score-company-csv", {
          method: "POST",
          body: formData,
        });

        const payload = (await response.json()) as ScoreResponse | { detail?: string };

        if (!response.ok) {
          throw new Error(
            "detail" in payload && payload.detail ? payload.detail : "Failed to score company CSV"
          );
        }

        setResult(payload as ScoreResponse);
      } catch (requestError) {
        setResult(null);
        setError(requestError instanceof Error ? requestError.message : "Failed to score company CSV");
      }
    });
  }

  return (
    <section className="rounded-[2rem] border border-[var(--line)] bg-[var(--panel)] p-8 shadow-[0_24px_80px_rgba(0,0,0,0.35)]">
      <div className="grid grid-cols-[0.9fr_1.1fr] gap-6">
        <div className="rounded-[1.8rem] border border-[var(--line)] bg-white/[0.02] p-7">
          <p className="text-[0.68rem] uppercase tracking-[0.26em] text-[var(--muted)]">Upload / Score</p>
          <h2 className="mt-5 text-3xl font-semibold tracking-[-0.05em] text-white">Score a company CSV</h2>
          <p className="mt-4 text-sm leading-8 text-[var(--muted)]">
            Upload a single-company CSV in the same schema expected by the backend. The UI sends the file to
            the local Next proxy, which forwards it to the Python API’s `/score-company-csv` endpoint.
          </p>

          <div className="mt-8 rounded-[1.6rem] border border-dashed border-[var(--line-strong)] bg-black/10 p-6">
            <label className="block text-[0.62rem] uppercase tracking-[0.22em] text-[var(--muted)]">
              CSV file
            </label>
            <input
              className="mt-4 block w-full rounded-2xl border border-[var(--line)] bg-black/20 px-4 py-4 text-sm text-white outline-none file:mr-4 file:rounded-xl file:border-0 file:bg-[var(--accent-soft)] file:px-4 file:py-2 file:text-xs file:font-semibold file:uppercase file:tracking-[0.16em] file:text-[var(--accent)]"
              type="file"
              accept=".csv,text/csv"
              onChange={(event) => {
                const file = event.target.files?.[0] ?? null;
                setSelectedFile(file);
                setError(null);
              }}
            />
            <div className="mt-5 flex items-center justify-between gap-4">
              <p className="text-sm text-[var(--muted)]">
                {selectedFile ? selectedFile.name : "No file selected yet."}
              </p>
              <button
                type="button"
                onClick={submitScore}
                disabled={isPending}
                className="rounded-2xl border border-[var(--accent-soft)] bg-[var(--accent-soft)] px-5 py-3 text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[var(--accent)] transition hover:border-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isPending ? "Scoring..." : "Run Score"}
              </button>
            </div>
          </div>

          <div className="mt-6 grid gap-3">
            <div className="rounded-2xl border border-[var(--line)] bg-black/10 p-4">
              <p className="text-[0.62rem] uppercase tracking-[0.18em] text-[var(--muted)]">Rendered output</p>
              <p className="mt-2 text-sm leading-7 text-white">
                probability, risk band, rule flags, top reasons, support summary, warnings
              </p>
            </div>
            <div className="rounded-2xl border border-[var(--line)] bg-black/10 p-4">
              <p className="text-[0.62rem] uppercase tracking-[0.18em] text-[var(--muted)]">Expected input</p>
              <p className="mt-2 text-sm leading-7 text-white">One company, one to three years, CSV only.</p>
            </div>
          </div>

          {error ? (
            <div className="mt-6 rounded-2xl border border-rose-500/20 bg-rose-500/5 p-4">
              <p className="text-[0.62rem] uppercase tracking-[0.18em] text-rose-200/70">Error</p>
              <p className="mt-2 text-sm leading-7 text-rose-100">{error}</p>
            </div>
          ) : null}
        </div>

        <div className="rounded-[1.8rem] border border-[var(--line)] bg-white/[0.02] p-7">
          {!result ? (
            <div className="flex h-full min-h-[720px] items-center justify-center rounded-[1.4rem] border border-[var(--line)] bg-black/10">
              <div className="max-w-md text-center">
                <p className="text-[0.68rem] uppercase tracking-[0.26em] text-[var(--muted)]">Scoring Output</p>
                <h3 className="mt-5 text-2xl font-semibold tracking-[-0.04em] text-white">
                  No score loaded yet
                </h3>
                <p className="mt-4 text-sm leading-8 text-[var(--muted)]">
                  Upload one of the curated demo CSVs or any valid single-company input, then run the score to
                  inspect the model output.
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-[1.1fr_0.9fr] gap-4">
                <div className="rounded-[1.4rem] border border-[var(--line)] bg-black/10 p-5">
                  <p className="text-[0.62rem] uppercase tracking-[0.2em] text-[var(--muted)]">Company</p>
                  <h3 className="mt-3 text-2xl font-semibold tracking-[-0.04em] text-white">
                    {result.company_name}
                  </h3>
                  <p className="mt-2 text-sm text-[var(--muted)]">{result.cin}</p>
                  <p className="mt-3 text-sm leading-7 text-[var(--muted)]">{result.framing_message}</p>
                </div>
                <div className="rounded-[1.4rem] border border-[var(--line)] bg-black/10 p-5">
                  <p className="text-[0.62rem] uppercase tracking-[0.2em] text-[var(--muted)]">Latest outcome</p>
                  <div className="mt-4 flex items-center gap-3">
                    <RiskBandPill band={result.risk_band} />
                    <span className="text-[0.7rem] uppercase tracking-[0.18em] text-[var(--muted)]">
                      {result.ml_class}
                    </span>
                  </div>
                  <div className="mt-5 grid grid-cols-2 gap-3">
                    <div>
                      <p className="text-[0.62rem] uppercase tracking-[0.16em] text-[var(--muted)]">
                        Probability
                      </p>
                      <p className="mt-2 text-2xl font-semibold text-white">
                        {formatMetric(result.ml_probability)}
                      </p>
                    </div>
                    <div>
                      <p className="text-[0.62rem] uppercase tracking-[0.16em] text-[var(--muted)]">
                        Threshold
                      </p>
                      <p className="mt-2 text-2xl font-semibold text-white">
                        {formatMetric(result.model_threshold)}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-4 gap-3">
                <div className="rounded-2xl border border-[var(--line)] bg-black/10 p-4">
                  <p className="text-[0.62rem] uppercase tracking-[0.16em] text-[var(--muted)]">Years</p>
                  <p className="mt-2 text-xl font-semibold text-white">{result.years_received}</p>
                </div>
                <div className="rounded-2xl border border-[var(--line)] bg-black/10 p-4">
                  <p className="text-[0.62rem] uppercase tracking-[0.16em] text-[var(--muted)]">Latest year</p>
                  <p className="mt-2 text-xl font-semibold text-white">{result.latest_financial_year}</p>
                </div>
                <div className="rounded-2xl border border-[var(--line)] bg-black/10 p-4">
                  <p className="text-[0.62rem] uppercase tracking-[0.16em] text-[var(--muted)]">Model</p>
                  <p className="mt-2 text-sm font-semibold uppercase tracking-[0.08em] text-white">
                    {result.model_name}
                  </p>
                </div>
                <div className="rounded-2xl border border-[var(--line)] bg-black/10 p-4">
                  <p className="text-[0.62rem] uppercase tracking-[0.16em] text-[var(--muted)]">Rule flags</p>
                  <p className="mt-2 text-xl font-semibold text-white">{result.rule_flag_count}</p>
                </div>
              </div>

              <div className="rounded-[1.4rem] border border-[var(--line)] bg-black/10 p-5">
                <p className="text-[0.62rem] uppercase tracking-[0.2em] text-[var(--muted)]">Support summary</p>
                <p className="mt-3 text-sm leading-8 text-white">{result.support_summary}</p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <section className="rounded-[1.4rem] border border-[var(--line)] bg-black/10 p-5">
                  <p className="text-[0.62rem] uppercase tracking-[0.2em] text-[var(--muted)]">Rule flags</p>
                  {result.rule_flags_triggered.length === 0 ? (
                    <p className="mt-4 text-sm text-[var(--muted)]">No rule-based flags were triggered.</p>
                  ) : (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {result.rule_flags_triggered.map((flag) => (
                        <span
                          key={flag}
                          className="rounded-full border border-[var(--line)] bg-white/[0.02] px-3 py-2 text-[0.7rem] tracking-[0.04em] text-white"
                        >
                          {flag}
                        </span>
                      ))}
                    </div>
                  )}
                </section>

                <section className="rounded-[1.4rem] border border-[var(--line)] bg-black/10 p-5">
                  <p className="text-[0.62rem] uppercase tracking-[0.2em] text-[var(--muted)]">Top reasons</p>
                  {result.top_reasons.length === 0 ? (
                    <p className="mt-4 text-sm text-[var(--muted)]">No explanatory reasons were returned.</p>
                  ) : (
                    <ul className="mt-4 space-y-3">
                      {result.top_reasons.map((reason) => (
                        <li key={reason} className="text-sm leading-7 text-white">
                          {reason}
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              </div>

              <section className="rounded-[1.4rem] border border-[var(--line)] bg-black/10 p-5">
                <p className="text-[0.62rem] uppercase tracking-[0.2em] text-[var(--muted)]">Warnings</p>
                {result.warnings.length === 0 ? (
                  <p className="mt-4 text-sm text-[var(--muted)]">No warnings returned by the backend.</p>
                ) : (
                  <ul className="mt-4 space-y-3">
                    {result.warnings.map((warning) => (
                      <li key={warning} className="text-sm leading-7 text-[var(--warm)]">
                        {warning}
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section className="rounded-[1.4rem] border border-[var(--line)] bg-black/10 p-5">
                <p className="text-[0.62rem] uppercase tracking-[0.2em] text-[var(--muted)]">Yearwise scores</p>
                <div className="mt-4 grid gap-3">
                  {result.yearwise_scores.map((yearScore) => (
                    <div
                      key={yearScore.financial_year}
                      className="grid grid-cols-[0.45fr_0.2fr_0.2fr_0.15fr] items-start gap-4 rounded-2xl border border-[var(--line)] bg-white/[0.02] p-4"
                    >
                      <div>
                        <p className="text-[0.62rem] uppercase tracking-[0.16em] text-[var(--muted)]">Year</p>
                        <p className="mt-2 text-lg font-semibold text-white">{yearScore.financial_year}</p>
                        <p className="mt-3 text-xs leading-6 text-[var(--muted)]">{yearScore.support_summary}</p>
                      </div>
                      <div>
                        <p className="text-[0.62rem] uppercase tracking-[0.16em] text-[var(--muted)]">
                          Probability
                        </p>
                        <p className="mt-2 text-lg font-semibold text-white">
                          {formatMetric(yearScore.ml_probability)}
                        </p>
                      </div>
                      <div>
                        <p className="text-[0.62rem] uppercase tracking-[0.16em] text-[var(--muted)]">
                          Imputed share
                        </p>
                        <p className="mt-2 text-lg font-semibold text-white">
                          {formatMetric(yearScore.imputed_feature_fraction)}
                        </p>
                      </div>
                      <div className="flex justify-end">
                        <RiskBandPill band={yearScore.risk_band} />
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
