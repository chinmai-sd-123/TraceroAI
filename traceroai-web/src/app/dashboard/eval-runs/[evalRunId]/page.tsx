import Link from "next/link";
import { notFound } from "next/navigation";

import { type ApiEvalRun, getEvalRun } from "@/lib/api";

export default async function EvalRunDetailPage({
  params,
}: {
  params: Promise<{ evalRunId: string }>;
}) {
  const { evalRunId } = await params;
  const run = await getEvalRun(evalRunId);

  if (!run) {
    notFound();
  }

  const passRate = toPercent(run.summary.pass_rate);

  return (
    <section>
      <div className="mb-6">
        <Link
          href="/dashboard/eval-runs"
          className="text-sm text-zinc-400 transition hover:text-zinc-100"
        >
          Back to eval runs
        </Link>
      </div>

      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-cyan-300">
            Eval Run Detail
          </p>
          <h1 className="mt-3 max-w-4xl text-3xl font-semibold leading-tight">
            {run.pipeline.pipeline_version}
          </h1>
          <p className="mt-3 font-mono text-xs text-zinc-500">
            {run.eval_run_id}
          </p>
        </div>

        <span className={statusClassName(run.status)}>
          {formatLabel(run.status)}
        </span>
      </div>

      <div className="mt-8 grid gap-4 md:grid-cols-4">
        <MetricCard label="Run type" value={formatLabel(run.run_type)} />
        <MetricCard label="Pass rate" value={`${passRate}%`} />
        <MetricCard
          label="Passed"
          value={`${run.summary.passed_cases}/${run.summary.total_cases}`}
        />
        <MetricCard label="Failed" value={String(run.summary.failed_cases)} />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_1fr]">
        <Panel title="Dataset">
          <Field label="Name" value={run.dataset.name} />
          <Field label="Dataset ID" value={run.dataset.dataset_id} />
          <Field label="Version" value={run.dataset.version || "unversioned"} />
        </Panel>

        <Panel title="Pipeline">
          <Field label="Version" value={run.pipeline.pipeline_version} />
          <Field
            label="Retrieval"
            value={run.pipeline.retrieval_strategy || "not recorded"}
          />
          <Field label="Model" value={run.pipeline.model || "not recorded"} />
          <Field
            label="Prompt"
            value={run.pipeline.prompt_version || "not recorded"}
          />
        </Panel>
      </div>

      <Panel title="Metrics" className="mt-6">
        {run.metrics.length > 0 ? (
          <div className="grid gap-3 md:grid-cols-3">
            {run.metrics.map((metric) => (
              <div
                key={metric.metric_name}
                className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-4"
              >
                <p className="text-xs uppercase tracking-wide text-zinc-500">
                  {formatLabel(metric.metric_name)}
                </p>
                <p className="mt-2 text-lg font-semibold">
                  {toPercent(metric.score)}%
                </p>
                <p className="mt-1 text-xs text-zinc-500">
                  threshold {toPercent(metric.threshold)}%
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-zinc-500">No metric summaries recorded.</p>
        )}
      </Panel>

      {run.run_type === "regression" ? (
        <RegressionCases run={run} />
      ) : (
        <ExperimentVariants run={run} />
      )}

      {run.summary.recommendation ? (
        <Panel title="Recommendation" className="mt-6">
          <p className="leading-7 text-zinc-300">{run.summary.recommendation}</p>
        </Panel>
      ) : null}
    </section>
  );
}

function RegressionCases({ run }: { run: ApiEvalRun }) {
  return (
    <Panel title="Case Results" className="mt-6">
      {run.cases.length > 0 ? (
        <div className="space-y-4">
          {run.cases.map((testCase) => (
            <div
              key={testCase.case_id}
              className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-4"
            >
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <p className="text-sm font-semibold text-zinc-100">
                    {testCase.question}
                  </p>
                  <p className="mt-1 font-mono text-xs text-zinc-500">
                    {testCase.case_id}
                  </p>
                </div>

                <span
                  className={
                    testCase.passed
                      ? "rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-xs font-medium text-emerald-300"
                      : "rounded-md border border-red-500/30 bg-red-500/10 px-2 py-1 text-xs font-medium text-red-300"
                  }
                >
                  {testCase.passed ? "passed" : "failed"}
                </span>
              </div>

              {testCase.failure_label ? (
                <p className="mt-3 text-sm text-red-300">
                  {formatLabel(testCase.failure_label)}
                </p>
              ) : null}

              {testCase.reason ? (
                <p className="mt-2 leading-6 text-zinc-400">{testCase.reason}</p>
              ) : null}

              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <Field
                  label="Expected"
                  value={testCase.expected_answer || "not recorded"}
                />
                <Field
                  label="Actual"
                  value={testCase.actual_answer || "not recorded"}
                />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-zinc-500">No case-level results recorded.</p>
      )}
    </Panel>
  );
}

function ExperimentVariants({ run }: { run: ApiEvalRun }) {
  return (
    <Panel title="Variant Comparison" className="mt-6">
      <div className="overflow-hidden rounded-lg border border-zinc-800">
        <div className="grid grid-cols-[1.2fr_120px_120px_120px] bg-zinc-950 px-4 py-3 text-xs font-medium uppercase tracking-wide text-zinc-500">
          <div>Variant</div>
          <div>Passed</div>
          <div>Failed</div>
          <div>Latency</div>
        </div>

        <div className="divide-y divide-zinc-800">
          {run.variants.map((variant) => (
            <div
              key={variant.variant_id}
              className="grid grid-cols-[1.2fr_120px_120px_120px] px-4 py-4 text-sm text-zinc-300"
            >
              <div>
                <p className="font-medium text-zinc-100">{variant.name}</p>
                <p className="mt-1 font-mono text-xs text-zinc-500">
                  {formatConfig(variant.config)}
                </p>
              </div>
              <div>{variant.passed_cases}</div>
              <div>{variant.failed_cases}</div>
              <div>{variant.average_latency_ms ?? 0}ms</div>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-5">
      <p className="text-sm text-zinc-500">{label}</p>
      <p className="mt-2 text-lg font-semibold">{value}</p>
    </div>
  );
}

function Panel({
  title,
  children,
  className = "",
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-lg border border-zinc-800 bg-zinc-900/60 p-6 ${className}`}>
      <h2 className="text-lg font-semibold">{title}</h2>
      <div className="mt-4">{children}</div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="mb-4 last:mb-0">
      <p className="text-xs uppercase tracking-wide text-zinc-500">{label}</p>
      <p className="mt-2 text-sm leading-6 text-zinc-300">{value}</p>
    </div>
  );
}

function statusClassName(status: string) {
  if (status === "completed") {
    return "inline-flex rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm font-medium text-emerald-300";
  }

  if (status === "failed") {
    return "inline-flex rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm font-medium text-red-300";
  }

  return "inline-flex rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm font-medium text-amber-300";
}

function formatLabel(label: string) {
  return label.replaceAll("_", " ");
}

function toPercent(score: number | null | undefined) {
  if (score == null) {
    return 0;
  }

  return Math.round(score * 100);
}

function formatConfig(config: Record<string, unknown>) {
  const entries = Object.entries(config);

  if (entries.length === 0) {
    return "no config recorded";
  }

  return entries.map(([key, value]) => `${key}=${String(value)}`).join(", ");
}
