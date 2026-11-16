import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { type ApiEvalRun, getEvalRun } from "@/lib/api";

import { CopyButton } from "@/components/copy-button";
import { CheckIcon, CrossIcon } from "@/components/icons";
import { DiagnosisBadge, PageFrame, PageHeader, Panel, formatMs } from "../../ui";

export default async function EvalRunDetailPage({
  params,
}: {
  params: Promise<{ evalRunId: string }>;
}) {
  const { evalRunId } = await params;
  const run = await getEvalRun(evalRunId);
  if (!run) notFound();

  const experiment = run.run_type !== "regression";

  return (
    <PageFrame>
      <PageHeader
        crumbs={[{ label: "Eval runs", href: "/dashboard/eval-runs" }, { label: run.eval_run_id }]}
        title={experiment ? `Experiment on ${run.dataset.name}` : run.pipeline.pipeline_version}
        description={
          <>
            {experiment ? run.pipeline.pipeline_version : `Regression run on ${run.dataset.name}`} ·{" "}
            {new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(run.timestamp))}
          </>
        }
        actions={
          <>
            <RunStatus status={run.status} />
            <CopyButton text={run.eval_run_id} label="Copy run id" />
          </>
        }
      />

      <dl className="mt-6 grid grid-cols-2 rounded border border-line sm:grid-cols-4">
        {experiment ? (
          <>
            <Figure label="Variants" value={String(run.variants.length)} />
            <Figure label="Questions" value={String(new Set(run.cases.map((c) => c.case_id)).size || run.summary.total_cases)} />
            <Figure label="Best variant" value={bestVariant(run)?.name ?? "—"} />
            <Figure label="Its pass rate" value={`${toPercent(run.summary.pass_rate)}%`} />
          </>
        ) : (
          <>
            <Figure label="Pass rate" value={`${toPercent(run.summary.pass_rate)}%`} />
            <Figure label="Passed" value={`${run.summary.passed_cases} of ${run.summary.total_cases}`} />
            <Figure label="Failed" value={String(run.summary.failed_cases)} />
            <Figure label="Run type" value="Regression" />
          </>
        )}
      </dl>

      <div className="mt-6 grid items-start gap-6 lg:grid-cols-2">
        <Panel title="Dataset">
          <Facts
            rows={[
              ["Name", run.dataset.name],
              ["Id", <code key="id" className="font-dash-mono text-[0.8125rem]">{run.dataset.dataset_id}</code>],
              ["Version", run.dataset.version || "Not versioned"],
            ]}
          />
        </Panel>
        <Panel title="Pipeline">
          <Facts
            rows={[
              ["Version", run.pipeline.pipeline_version],
              ["Retrieval", run.pipeline.retrieval_strategy || "Not recorded"],
              ["Model", run.pipeline.model || "Not recorded"],
              ["Prompt", run.pipeline.prompt_version || "Not recorded"],
            ]}
          />
        </Panel>
      </div>

      {run.summary.recommendation && (
        <section className="mt-6 rounded border border-pass/40 bg-pass-soft px-5 py-4">
          <h2 className="font-semibold text-pass">Recommendation</h2>
          <p className="mt-1 max-w-[75ch] text-sm leading-6">{run.summary.recommendation}</p>
        </section>
      )}

      {run.metrics.length > 0 && (
        <Panel title="Metrics" className="mt-6" flush>
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-y border-line-strong bg-sunken text-left text-xs text-ink-muted">
                <th scope="col" className="px-5 py-2 font-medium">Metric</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Score</th>
                <th scope="col" className="px-5 py-2 text-right font-medium">Threshold</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {run.metrics.map((m) => {
                const met = m.threshold == null || (m.score ?? 0) >= m.threshold;
                return (
                  <tr key={m.metric_name}>
                    <td className="px-5 py-2.5">{m.metric_name.replaceAll("_", " ")}</td>
                    <td className={`px-3 py-2.5 text-right font-semibold ${met ? "text-pass" : "text-warn"}`}>
                      {toPercent(m.score)}%
                    </td>
                    <td className="px-5 py-2.5 text-right text-ink-muted">
                      {m.threshold == null ? "—" : `${toPercent(m.threshold)}%`}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Panel>
      )}

      {experiment ? (
        <>
          <ExperimentVariants run={run} />
          <CaseGrid run={run} />
        </>
      ) : (
        <RegressionCases run={run} />
      )}
    </PageFrame>
  );
}

function RunStatus({ status }: { status: string }) {
  const tone =
    status === "completed" ? "border-pass text-pass" : status === "failed" ? "border-warn text-warn" : "border-ink-faint text-ink-muted";
  return (
    <span className={`rounded-[3px] border px-1.5 py-0.5 text-xs font-semibold ${tone}`}>
      {status.charAt(0).toUpperCase() + status.slice(1).replaceAll("_", " ")}
    </span>
  );
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-line px-5 py-4 max-sm:[&:nth-child(n+3)]:border-t sm:[&:not(:first-child)]:border-l max-sm:[&:nth-child(even)]:border-l">
      <dt className="text-sm text-ink-muted">{label}</dt>
      <dd className="mt-1 text-xl font-semibold tracking-[-0.01em]">{value}</dd>
    </div>
  );
}

function Facts({ rows }: { rows: Array<[string, ReactNode]> }) {
  return (
    <dl className="grid grid-cols-[6rem_minmax(0,1fr)] gap-y-1.5 text-sm">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-ink-muted">{k}</dt>
          <dd className="break-words">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function RegressionCases({ run }: { run: ApiEvalRun }) {
  return (
    <Panel title="Cases" description={`${run.cases.length} labelled questions.`} className="mt-6" flush>
      {run.cases.length === 0 ? (
        <p className="px-5 pb-5 text-sm text-ink-muted">No case-level results were recorded.</p>
      ) : (
        <ul className="divide-y divide-line border-t border-line">
          {run.cases.map((c) => (
            <li key={c.case_id} className="px-5 py-4">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <p className="font-medium">{c.question}</p>
                <span className={`text-sm font-semibold ${c.passed ? "text-pass" : "text-ink"}`}>
                  {c.passed ? "Passed" : "Failed"}
                </span>
              </div>
              <p className="mt-0.5 font-dash-mono text-xs text-ink-muted">{c.case_id}</p>
              {c.failure_label && (
                <p className="mt-2">
                  <DiagnosisBadge label={c.failure_label} size="sm" />
                </p>
              )}
              {c.reason && <p className="mt-2 max-w-[75ch] text-sm text-ink-muted">{c.reason}</p>}
              {(c.expected_answer || c.actual_answer) && (
                <dl className="mt-3 grid gap-4 text-sm md:grid-cols-2">
                  <div>
                    <dt className="text-xs text-ink-muted">Expected</dt>
                    <dd className="mt-0.5">{c.expected_answer || "Not recorded"}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-ink-muted">Actual</dt>
                    <dd className="mt-0.5">{c.actual_answer || "Not recorded"}</dd>
                  </div>
                </dl>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

// Answers a variant produced: graded ones plus any the judge couldn't grade.
function answersOf(v: ApiEvalRun["variants"][number]) {
  const ungradeable = Number((v.config as { ungradeable_cases?: unknown })?.ungradeable_cases) || 0;
  return v.passed_cases + v.failed_cases + ungradeable;
}

function formatUsd(usd: number) {
  return usd < 1 ? `${(usd * 100).toFixed(usd < 0.01 ? 3 : 2)}¢` : `$${usd.toFixed(2)}`;
}

function ExperimentVariants({ run }: { run: ApiEvalRun }) {
  const best = Math.max(...run.variants.map((v) => v.passed_cases));
  // Only when the SDK reported usage (generate() returned it).
  const showUsage = run.variants.some((v) => v.prompt_tokens != null);
  return (
    <Panel title="Variants" description="Each variant answered the same labelled questions." className="mt-6" flush>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[36rem] border-collapse text-sm">
          <thead>
            <tr className="border-y border-line-strong bg-sunken text-left text-xs text-ink-muted">
              <th scope="col" className="px-5 py-2 font-medium">Variant</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Passed</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Failed</th>
              <th scope="col" className="px-5 py-2 text-right font-medium">Average latency</th>
              {showUsage && (
                <>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Tokens per answer</th>
                  <th scope="col" className="px-5 py-2 text-right font-medium">Cost per correct answer</th>
                </>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {run.variants.map((v) => (
              <tr key={v.variant_id}>
                <td className="px-5 py-3">
                  <p className="font-medium">{v.name}</p>
                  {formatConfig(v.config) !== v.name && (
                    <p className="mt-0.5 font-dash-mono text-xs text-ink-muted">{formatConfig(v.config)}</p>
                  )}
                </td>
                <td className={`px-3 py-3 text-right font-semibold ${v.passed_cases === best ? "text-pass" : ""}`}>
                  {v.passed_cases}
                </td>
                <td className="px-3 py-3 text-right text-ink-muted">{v.failed_cases}</td>
                <td className="px-5 py-3 text-right text-ink-muted">{formatMs(v.average_latency_ms)}</td>
                {showUsage && (
                  <>
                    <td className="px-3 py-3 text-right text-ink-muted tabular-nums">
                      {v.prompt_tokens != null && answersOf(v) > 0
                        ? Math.round(((v.prompt_tokens ?? 0) + (v.completion_tokens ?? 0)) / answersOf(v)).toLocaleString()
                        : "not reported"}
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums">
                      {v.cost_usd != null && v.passed_cases > 0
                        ? formatUsd(v.cost_usd / v.passed_cases)
                        : v.cost_usd != null
                          ? "no correct answers"
                          : v.prompt_tokens != null
                            ? "model not priced"
                            : "not reported"}
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

/** Questions down the side, variants across: which variant got which
 * question right. Questions the variants disagree on come first, since they
 * are where the variants actually differ. */
function CaseGrid({ run }: { run: ApiEvalRun }) {
  const cases = run.cases.filter((c) => c.variant_id);
  if (cases.length === 0) {
    return (
      <p className="mt-4 text-sm text-ink-muted">
        This run has no per-question results; experiments record them from SDK 0.5 on.
      </p>
    );
  }
  const byQuestion = new Map<string, { question: string; expected?: string | null; cells: Map<string, (typeof cases)[number]> }>();
  for (const c of cases) {
    const row = byQuestion.get(c.case_id) ?? { question: c.question, expected: c.expected_answer, cells: new Map() };
    row.cells.set(c.variant_id!, c);
    byQuestion.set(c.case_id, row);
  }
  const rows = [...byQuestion.entries()].map(([caseId, row]) => {
    const verdicts = new Set([...row.cells.values()].map((c) => c.passed));
    return { caseId, ...row, disagree: verdicts.size > 1 };
  });
  rows.sort((a, b) => Number(b.disagree) - Number(a.disagree));
  const disagreements = rows.filter((r) => r.disagree).length;

  return (
    <Panel
      title="Questions"
      description={`${rows.length} question${rows.length === 1 ? "" : "s"}; the variants disagree on ${disagreements}.`}
      className="mt-6"
      flush
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[36rem] border-collapse text-sm">
          <thead>
            <tr className="border-y border-line-strong bg-sunken text-left text-xs text-ink-muted">
              <th scope="col" className="px-5 py-2 font-medium">Question</th>
              {run.variants.map((v) => (
                <th key={v.variant_id} scope="col" className="px-3 py-2 text-center font-medium whitespace-nowrap">
                  {v.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((row) => (
              <tr key={row.caseId} className={row.disagree ? "" : "text-ink-muted"}>
                <th scope="row" className="max-w-0 px-5 py-2.5 text-left font-normal w-1/2">
                  <span className={`block truncate ${row.disagree ? "font-medium text-ink" : ""}`} title={row.question}>
                    {row.question}
                  </span>
                  {row.expected && (
                    <span className="block truncate text-xs text-ink-muted" title={row.expected}>
                      Expected: {row.expected}
                    </span>
                  )}
                </th>
                {run.variants.map((v) => {
                  const cell = row.cells.get(v.variant_id);
                  const content = !cell ? (
                    <span className="text-xs text-ink-muted">not graded</span>
                  ) : cell.passed ? (
                    <span className="inline-flex items-center gap-1 font-medium text-pass">
                      <CheckIcon size={14} /> Correct
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 font-medium text-ink">
                      <CrossIcon size={14} /> Wrong
                    </span>
                  );
                  return (
                    <td key={v.variant_id} className="px-3 py-2.5 text-center" title={cell?.actual_answer ?? undefined}>
                      {cell?.trace_id ? (
                        <Link href={`/dashboard/traces/${cell.trace_id}`} className="hover:underline">
                          {content}
                        </Link>
                      ) : (
                        content
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

/** The variant with the most passed cases (ties: lower latency), as the SDK picks it. */
function bestVariant(run: ApiEvalRun) {
  return [...run.variants].sort(
    (a, b) =>
      b.passed_cases / Math.max(1, b.passed_cases + b.failed_cases) -
        a.passed_cases / Math.max(1, a.passed_cases + a.failed_cases) ||
      (a.average_latency_ms ?? 0) - (b.average_latency_ms ?? 0),
  )[0];
}

function toPercent(score: number | null | undefined) {
  return score == null ? 0 : Math.round(score * 100);
}

// Internal bookkeeping keys that aren't real pipeline knobs, hidden from the
// readable config string.
const NON_CONFIG_KEYS = new Set(["ungradeable_cases"]);

function formatConfig(config: Record<string, unknown>) {
  const entries = Object.entries(config).filter(([key]) => !NON_CONFIG_KEYS.has(key));
  if (entries.length === 0) return "No config recorded";
  return entries.map(([key, value]) => `${key}=${String(value)}`).join(", ");
}
