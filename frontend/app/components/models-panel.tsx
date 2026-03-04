"use client";

import { useEffect, useState } from "react";

type JsonValue = string | number | boolean | null | undefined | JsonValue[] | Record<string, JsonValue>;

type ModelRecord = {
  model_name: string;
  is_production: boolean;
  artifact_paths: Record<string, JsonValue>;
  leaderboard_metrics: Record<string, JsonValue>;
  threshold_config: Record<string, JsonValue>;
  feature_config: Record<string, JsonValue>;
  validation_metrics: Record<string, JsonValue>;
  test_metrics: Record<string, JsonValue>;
};

type CatalogResponse = {
  status: string;
  production_model: string;
  model_count: number;
  models: ModelRecord[];
};

function metric(value: unknown, digits = 3) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return value.toFixed(digits);
}

function asString(value: JsonValue) {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (value == null) {
    return "n/a";
  }
  return JSON.stringify(value);
}

function renderSimpleValue(value: JsonValue) {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value.toString() : "n/a";
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  if (value == null) {
    return "n/a";
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return "[]";
    }
    return value.join(", ");
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return value;
}

function interpretationFor(model: ModelRecord) {
  const validationPrAuc = Number(model.validation_metrics?.pr_auc ?? 0);
  const validationRecall = Number(model.validation_metrics?.recall ?? 0);
  const validationPrecision = Number(model.validation_metrics?.precision ?? 0);
  const validationBrier = Number(model.validation_metrics?.brier_score ?? 1);
  const testPrAuc = Number(model.test_metrics?.pr_auc ?? 0);

  if (model.is_production) {
    return "Current production model. It leads the active registry under the latest selection policy and is the model the scoring API uses by default.";
  }
  if (validationRecall >= 0.9 && validationPrecision < 0.86) {
    return "Recall-heavy challenger. It catches more positive cases, but it trades away precision compared with the current production model.";
  }
  if (validationPrAuc >= 0.88 && validationBrier < 0.16 && testPrAuc >= 0.92) {
    return "Balanced challenger. It remains competitive on ranking and calibration, but it was not selected under the current production rule.";
  }
  return "Comparison model. Keep it in the registry as a benchmark as the dataset grows and model selection is revisited.";
}

function KeyValueGrid({
  title,
  data,
}: {
  title: string;
  data: Record<string, JsonValue>;
}) {
  const entries = Object.entries(data ?? {});

  return (
    <section className="rounded-[1.4rem] border border-[var(--line)] bg-black/10 p-5">
      <p className="text-[0.62rem] uppercase tracking-[0.22em] text-[var(--muted)]">{title}</p>
      {entries.length === 0 ? (
        <p className="mt-4 text-sm text-[var(--muted)]">No values available.</p>
      ) : (
        <div className="mt-4 grid grid-cols-2 gap-x-5 gap-y-3">
          {entries.map(([key, value]) => (
            <div key={key} className="border-b border-[var(--line)] pb-3">
              <p className="text-[0.62rem] uppercase tracking-[0.18em] text-[var(--muted)]">{key}</p>
              <p className="mt-2 break-words text-sm leading-6 text-white">{renderSimpleValue(value)}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function ArrayBlock({
  title,
  values,
}: {
  title: string;
  values: string[];
}) {
  return (
    <section className="rounded-[1.4rem] border border-[var(--line)] bg-black/10 p-5">
      <p className="text-[0.62rem] uppercase tracking-[0.22em] text-[var(--muted)]">{title}</p>
      {values.length === 0 ? (
        <p className="mt-4 text-sm text-[var(--muted)]">No values available.</p>
      ) : (
        <div className="mt-4 flex flex-wrap gap-2">
          {values.map((value) => (
            <span
              key={value}
              className="rounded-full border border-[var(--line)] bg-white/[0.02] px-3 py-2 text-[0.7rem] tracking-[0.04em] text-white"
            >
              {value}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}

export function ModelsPanel() {
  const [data, setData] = useState<CatalogResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const response = await fetch("/api/models", { cache: "no-store" });
        const payload = (await response.json()) as CatalogResponse | { detail?: string; status?: string };

        if (!response.ok) {
          throw new Error(
            "detail" in payload && payload.detail ? payload.detail : "Failed to load model catalog"
          );
        }

        if (active) {
          setData(payload as CatalogResponse);
          setError(null);
        }
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load model catalog");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return (
      <section className="rounded-[2rem] border border-[var(--line)] bg-[var(--panel)] p-8 shadow-[0_24px_80px_rgba(0,0,0,0.35)]">
        <p className="text-sm uppercase tracking-[0.28em] text-[var(--muted)]">Model Registry</p>
        <div className="mt-8 h-40 animate-pulse rounded-3xl border border-[var(--line)] bg-white/[0.02]" />
      </section>
    );
  }

  if (error || !data) {
    return (
      <section className="rounded-[2rem] border border-rose-500/20 bg-rose-500/5 p-8 shadow-[0_24px_80px_rgba(0,0,0,0.35)]">
        <p className="text-sm uppercase tracking-[0.28em] text-rose-200/70">Model Registry</p>
        <h2 className="mt-6 text-2xl font-semibold text-white">Model catalog unavailable</h2>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-rose-100/70">
          {error ?? "The frontend proxy could not load the Fulcrum backend model catalog."}
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-[2rem] border border-[var(--line)] bg-[var(--panel)] p-8 shadow-[0_24px_80px_rgba(0,0,0,0.35)]">
      <div className="grid grid-cols-[1.45fr_0.55fr] gap-6">
        <div>
          <p className="text-sm uppercase tracking-[0.28em] text-[var(--muted)]">API Response Surface</p>
          <h2 className="mt-5 text-3xl font-semibold tracking-[-0.04em] text-white">
            Full trained-model registry, exposed directly from the backend.
          </h2>
          <p className="mt-4 max-w-4xl text-sm leading-8 text-[var(--muted)]">
            This page mirrors the `/models` endpoint and renders the full comparison dataset: top-level
            registry metadata, production selection, thresholds, feature schema information, and full
            validation/test metrics for each trained model.
          </p>
        </div>

        <div className="grid gap-3">
          <div className="rounded-[1.4rem] border border-[var(--line)] bg-white/[0.018] p-5">
            <p className="text-[0.62rem] uppercase tracking-[0.22em] text-[var(--muted)]">status</p>
            <p className="mt-3 text-2xl font-semibold tracking-[-0.04em] text-white">{data.status}</p>
          </div>
          <div className="rounded-[1.4rem] border border-[var(--line)] bg-white/[0.018] p-5">
            <p className="text-[0.62rem] uppercase tracking-[0.22em] text-[var(--muted)]">production_model</p>
            <p className="mt-3 text-xl font-semibold tracking-[-0.03em] text-[var(--accent)]">
              {data.production_model}
            </p>
          </div>
          <div className="rounded-[1.4rem] border border-[var(--line)] bg-white/[0.018] p-5">
            <p className="text-[0.62rem] uppercase tracking-[0.22em] text-[var(--muted)]">model_count</p>
            <p className="mt-3 text-2xl font-semibold tracking-[-0.04em] text-white">{data.model_count}</p>
          </div>
        </div>
      </div>

      <div className="mt-10 space-y-6">
        {data.models.map((model) => {
          const inputColumns = Array.isArray(model.feature_config?.input_columns)
            ? (model.feature_config.input_columns as string[])
            : [];
          const transformedColumns = Array.isArray(model.feature_config?.transformed_feature_names)
            ? (model.feature_config.transformed_feature_names as string[])
            : [];

          return (
            <article
              key={model.model_name}
              className={`rounded-[1.8rem] border p-7 ${
                model.is_production
                  ? "border-[var(--line-strong)] bg-[linear-gradient(135deg,rgba(140,240,204,0.08),rgba(255,255,255,0.015))]"
                  : "border-[var(--line)] bg-white/[0.018]"
              }`}
            >
              <div className="flex items-start justify-between gap-8">
                <div>
                  <div className="flex items-center gap-3">
                    <h3 className="text-2xl font-semibold tracking-[-0.04em] text-white">{model.model_name}</h3>
                    {model.is_production ? (
                      <span className="rounded-full border border-[var(--accent-soft)] bg-[var(--accent-soft)] px-3 py-1 text-[0.62rem] font-semibold uppercase tracking-[0.18em] text-[var(--accent)]">
                        Production
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-4 max-w-4xl text-sm leading-8 text-[var(--muted)]">{interpretationFor(model)}</p>
                </div>

                <div className="grid grid-cols-4 gap-3">
                  <div className="rounded-2xl border border-[var(--line)] bg-black/10 px-4 py-3">
                    <p className="text-[0.62rem] uppercase tracking-[0.2em] text-[var(--muted)]">Val PR-AUC</p>
                    <p className="mt-2 text-lg font-semibold text-white">
                      {metric(model.validation_metrics?.pr_auc)}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-[var(--line)] bg-black/10 px-4 py-3">
                    <p className="text-[0.62rem] uppercase tracking-[0.2em] text-[var(--muted)]">Val Recall</p>
                    <p className="mt-2 text-lg font-semibold text-white">
                      {metric(model.validation_metrics?.recall)}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-[var(--line)] bg-black/10 px-4 py-3">
                    <p className="text-[0.62rem] uppercase tracking-[0.2em] text-[var(--muted)]">Test PR-AUC</p>
                    <p className="mt-2 text-lg font-semibold text-white">
                      {metric(model.test_metrics?.pr_auc)}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-[var(--line)] bg-black/10 px-4 py-3">
                    <p className="text-[0.62rem] uppercase tracking-[0.2em] text-[var(--muted)]">Threshold</p>
                    <p className="mt-2 text-lg font-semibold text-white">
                      {metric(model.threshold_config?.threshold)}
                    </p>
                  </div>
                </div>
              </div>

              <div className="mt-7 grid grid-cols-2 gap-4">
                <KeyValueGrid title="threshold_config" data={model.threshold_config} />
                <KeyValueGrid title="leaderboard_metrics" data={model.leaderboard_metrics} />
              </div>

              <div className="mt-4 grid grid-cols-2 gap-4">
                <KeyValueGrid title="validation_metrics" data={model.validation_metrics} />
                <KeyValueGrid title="test_metrics" data={model.test_metrics} />
              </div>

              <div className="mt-4 grid grid-cols-2 gap-4">
                <ArrayBlock title="feature_config.input_columns" values={inputColumns} />
                <ArrayBlock title="feature_config.transformed_feature_names" values={transformedColumns} />
              </div>

              <div className="mt-4 rounded-[1.4rem] border border-[var(--line)] bg-black/10 p-5">
                <p className="text-[0.62rem] uppercase tracking-[0.22em] text-[var(--muted)]">
                  feature_config.summary
                </p>
                <div className="mt-4 grid grid-cols-3 gap-4">
                  <div>
                    <p className="text-[0.62rem] uppercase tracking-[0.18em] text-[var(--muted)]">
                      model_name
                    </p>
                    <p className="mt-2 text-sm text-white">{asString(model.feature_config?.model_name)}</p>
                  </div>
                  <div>
                    <p className="text-[0.62rem] uppercase tracking-[0.18em] text-[var(--muted)]">
                      feature_list_version
                    </p>
                    <p className="mt-2 text-sm text-white">
                      {asString(model.feature_config?.feature_list_version)}
                    </p>
                  </div>
                  <div>
                    <p className="text-[0.62rem] uppercase tracking-[0.18em] text-[var(--muted)]">
                      counts
                    </p>
                    <p className="mt-2 text-sm text-white">
                      {inputColumns.length} input / {transformedColumns.length} transformed
                    </p>
                  </div>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
