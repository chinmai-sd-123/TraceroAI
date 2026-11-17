import { cookies } from "next/headers";
import Link from "next/link";
import type { ReactNode } from "react";

import {
  TIME_RANGES,
  type TraceSummary,
  getEvalRuns,
  getIssues,
  getRecoveryRuns,
  type RecoveryRun,
  getSummary,
  getTimeseries,
  getTraces,
  parseRange,
  rangeSince,
} from "@/lib/api";
import type { ExperimentEvalRun } from "@/lib/eval-run-types";
import type { Trace } from "@/lib/trace-types";

import { LAYOUT_COOKIE, parseLayout } from "@/lib/layout-prefs";

import { LatencyChart, MiniBars, VolumeChart } from "./charts";
import { IssueList } from "./issues/issue-list";
import { CustomizeButton, LayoutEditor, PanelGrid, type PanelDef } from "./panel-grid";
import { actionWords } from "./recovery-runs/recovery";
import {
  DiagnosisBadge,
  EmptyState,
  PageFrame,
  PageHeader,
  Panel,
  ProvenanceMark,
  Segmented,
  StageSequence,
  diagnosisName,
  diagnosisTone,
  formatMs,
  formatWhen,
  hrefWith,
  isHealthy,
} from "./ui";

// Panels that need each trace's details read only the latest traces; headline
// numbers come from the API's summary over every trace in the range.
const RECENT_LIMIT = 200;

const OUTCOME_ORDER = [
  "healthy_answer",
  "correct_refusal",
  "retrieval_miss",
  "low_context_relevance",
  "unsupported_claim",
  "wrong_answer",
  "needs_review",
];

function percent(part: number, whole: number) {
  return whole === 0 ? "—" : `${Math.round((part / whole) * 100)}%`;
}

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ project?: string; range?: string }>;
}) {
  const params = await searchParams;
  const project = params.project;
  const range = parseRange(params.range);
  const [summary, series, recent, evalRuns, runs, cookieStore, issues] = await Promise.all([
    getSummary(project, range),
    getTimeseries(project, range),
    getTraces({
      projectId: project,
      limit: RECENT_LIMIT,
      since: rangeSince(range),
    }),
    getEvalRuns(project),
    getRecoveryRuns(project, { range, limit: 200 }),
    cookies(),
    getIssues(project, { range, limit: 200 }),
  ]);
  const savedLayout = parseLayout(cookieStore.get(LAYOUT_COOKIE)?.value).overview;
  // Regressed first, then open (the API's order); resolved ones don't need attention.
  const attention = issues?.filter((i) => i.status !== "resolved") ?? null;
  const regressedCount = attention?.filter((i) => i.status === "regressed").length ?? 0;
  const traces = recent.traces;
  const total = summary?.total ?? 0;
  const healthy = summary?.healthy ?? 0;
  // Health is over diagnosed runs only: agent runs aren't diagnosed yet.
  const diagnosed = total - (summary?.notDiagnosed ?? 0);
  const avgCost = summary?.costUsd.avg;
  const showCost = process.env.NEXT_PUBLIC_SHOW_COST !== "false" && avgCost != null;
  const latestExperiment = [...evalRuns.experimentRuns].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
  )[0];
  const recovery = runs && runs.length > 0 ? getRecoveryInsights(runs) : null;
  const buckets = series?.buckets ?? [];
  const rangeLabel = TIME_RANGES[range].label.toLowerCase();

  return (
    <LayoutEditor>
      <PageFrame>
        <PageHeader
          title="Overview"
          description={project ? `How answers are doing in ${project}.` : "How answers are doing across all projects."}
          actions={
            <div className="flex flex-wrap items-center gap-3">
              {total > 0 && <CustomizeButton />}
              <Segmented
                label="Time range"
                active={range}
                options={Object.keys(TIME_RANGES).map((key) => ({
                  key,
                  label: key === "all" ? "All" : key,
                  href: hrefWith("/dashboard", {
                    project,
                    range: key === "7d" ? undefined : key,
                  }),
                }))}
              />
            </div>
          }
        />

        {total === 0 ? (
          <div className="mt-6">
            <EmptyState title={range === "all" ? "No traces yet" : `No traces in the ${rangeLabel}`}>
              {range === "all" ? (
                <>
                  Send one with the Python SDK and it appears here within seconds.{" "}
                  <Link href="/docs/instrument/python-sdk" className="text-accent underline">
                    See how
                  </Link>
                  .
                </>
              ) : (
                <Link href={hrefWith("/dashboard", { project, range: "all" })} className="text-accent underline">
                  Show all time
                </Link>
              )}
            </EmptyState>
          </div>
        ) : (
          <div className="mt-6 space-y-6">
            <MetricRow>
              <Metric
                label="Traces"
                value={total.toLocaleString()}
                detail={TIME_RANGES[range].label}
                chart={<MiniBars values={buckets.map((b) => b.total)} />}
              />
              <Metric
                label="Healthy"
                value={percent(healthy, diagnosed)}
                detail={`${healthy.toLocaleString()} of ${diagnosed.toLocaleString()}${diagnosed < total ? " diagnosed" : ""}`}
                chart={
                  <MiniBars
                    tone="pass"
                    values={buckets.map((b) => (b.total - b.notDiagnosed ? b.healthy / (b.total - b.notDiagnosed) : null))}
                  />
                }
              />
              <Metric
                label="Not healthy"
                value={(diagnosed - healthy).toLocaleString()}
                detail={
                  <Link href={hrefWith("/dashboard/traces", { project })} className="text-accent hover:underline">
                    Investigate
                  </Link>
                }
                chart={<MiniBars values={buckets.map((b) => b.total - b.healthy - b.notDiagnosed)} />}
              />
              <Metric
                label="p95 latency"
                value={formatMs(summary?.latencyMs.p95)}
                detail={summary?.latencyMs.avg ? `average ${formatMs(summary.latencyMs.avg)}` : "not measured"}
                chart={<MiniBars values={buckets.map((b) => b.p95Ms)} />}
              />
              {showCost && avgCost != null && (
                <Metric label="Cost per trace" value={`$${avgCost.toFixed(5)}`} detail="where tokens were logged" />
              )}
            </MetricRow>

            <PanelGrid
              defaults={OVERVIEW_PANELS}
              initial={savedLayout}
              panels={{
                volume: (
                  <Panel
                    title="Traces over time"
                    description={`Per ${series?.bucket ?? "day"}${range === "all" ? ", last 90 days" : ""}.`}
                  >
                    {series ? <VolumeChart buckets={buckets} bucket={series.bucket} /> : <Unavailable />}
                  </Panel>
                ),
                outcomes: (
                  <Panel title="Outcomes" description="By diagnosis.">
                    <Outcomes summary={summary} project={project} />
                  </Panel>
                ),
                issues: (
                  <Panel
                    title="Issues"
                    description={
                      attention === null
                        ? "Failing traces grouped by cause."
                        : `${attention.length} need${attention.length === 1 ? "s" : ""} attention in this range${
                            regressedCount ? `, ${regressedCount} regressed` : ""
                          }. Grouped by what failed and where.`
                    }
                    flush
                    actions={
                      <Link href={hrefWith("/dashboard/issues", { project })} className="text-sm text-accent hover:underline">
                        All issues
                      </Link>
                    }
                  >
                    {attention === null ? (
                      <Unavailable />
                    ) : attention.length === 0 ? (
                      <p className="px-5 pb-5 text-sm text-ink-muted">No open issues in this range.</p>
                    ) : (
                      <IssueList issues={attention.slice(0, 5)} compact />
                    )}
                  </Panel>
                ),
                failures: (
                  <Panel
                    title="Recent failures"
                    description="The latest traces that weren't healthy, with the stage that broke."
                    flush
                    actions={
                      <Link
                        href={hrefWith("/dashboard/traces", { project })}
                        className="text-sm text-accent hover:underline"
                      >
                        All traces
                      </Link>
                    }
                  >
                    <RecentFailures traces={traces} />
                  </Panel>
                ),
                latency: (
                  <Panel title="p95 latency" description={`Per ${series?.bucket ?? "day"}.`}>
                    {series ? <LatencyChart buckets={buckets} bucket={series.bucket} height={180} /> : <Unavailable />}
                  </Panel>
                ),
                coverage: (
                  <Panel title="How sure the diagnoses are" description="Which check decided each diagnosis.">
                    <Coverage summary={summary} />
                  </Panel>
                ),
                experiment: (
                  <Panel title="Latest experiment">
                    <LatestExperiment run={latestExperiment} />
                  </Panel>
                ),
                recovery: recovery ? (
                  <Panel
                    title="Self-healing recovery"
                    description={`${recovery.runs} recovery run${recovery.runs === 1 ? "" : "s"} in this range, judged by each run's final attempt.`}
                    actions={
                      <Link
                        href={hrefWith("/dashboard/recovery-runs", { project })}
                        className="text-sm text-accent hover:underline"
                      >
                        All runs
                      </Link>
                    }
                  >
                    <RecoveryInsights insights={recovery} />
                  </Panel>
                ) : null,
              }}
            />
          </div>
        )}
      </PageFrame>
    </LayoutEditor>
  );
}

// The overview's panels and their default widths (of 12 columns). The viewer
// can resize, reorder and hide them; see panel-grid.tsx.
const OVERVIEW_PANELS: PanelDef[] = [
  { id: "volume", title: "Traces over time", size: 8 },
  { id: "outcomes", title: "Outcomes", size: 4 },
  { id: "issues", title: "Issues", size: 12 },
  { id: "failures", title: "Recent failures", size: 6 },
  { id: "latency", title: "p95 latency", size: 6 },
  { id: "coverage", title: "How sure the diagnoses are", size: 6 },
  { id: "experiment", title: "Latest experiment", size: 6 },
  { id: "recovery", title: "Self-healing recovery", size: 12 },
];

function Unavailable() {
  return <p className="py-10 text-center text-sm text-ink-muted">Couldn&apos;t load this chart from the API.</p>;
}

// --- headline numbers -------------------------------------------------------------

function MetricRow({ children }: { children: ReactNode }) {
  return (
    <dl className="grid grid-cols-2 rounded border border-line bg-surface sm:grid-cols-3 lg:auto-cols-fr lg:grid-flow-col lg:grid-cols-none">
      {children}
    </dl>
  );
}

function Metric({
  label,
  value,
  detail,
  chart,
}: {
  label: string;
  value: string;
  detail?: ReactNode;
  chart?: ReactNode;
}) {
  return (
    <div className="flex flex-col border-line px-5 py-4 max-lg:border-b lg:[&:not(:first-child)]:border-l max-lg:[&:nth-child(odd)]:border-r sm:max-lg:[&:nth-child(odd)]:border-r-0 sm:max-lg:[&:not(:nth-child(3n+1))]:border-l">
      <dt className="text-sm text-ink-muted">{label}</dt>
      <dd className="mt-1 text-2xl font-semibold tracking-[-0.015em]">{value}</dd>
      {detail && <dd className="mt-0.5 text-xs text-ink-muted">{detail}</dd>}
      {chart && <dd className="mt-3">{chart}</dd>}
    </div>
  );
}

// --- panels --------------------------------------------------------------------

const TONE_BAR = {
  pass: "bg-pass",
  cause: "bg-cause",
  warn: "bg-warn",
  none: "bg-line-strong",
};

function outcomeRank(label: string) {
  const index = OUTCOME_ORDER.indexOf(label);
  return index === -1 ? OUTCOME_ORDER.length : index;
}

function Outcomes({ summary, project }: { summary: TraceSummary | null; project?: string }) {
  if (!summary) return null;
  const rows = Object.entries(summary.byDiagnosis).sort(([a], [b]) => outcomeRank(a) - outcomeRank(b));
  const max = Math.max(1, ...rows.map(([, count]) => count));
  return (
    <ul className="-mx-2">
      {rows.map(([label, count]) => (
        <li key={label}>
          <Link
            href={hrefWith("/dashboard/traces", { project, diagnosis: label })}
            className="grid grid-cols-[8rem_1fr_3rem] items-center gap-3 rounded px-2 py-1.5 hover:bg-sunken"
          >
            <span className="truncate text-sm">{diagnosisName(label)}</span>
            <span className="h-2 bg-sunken">
              <span
                className={`block h-2 ${TONE_BAR[diagnosisTone(label)]}`}
                style={{ width: `${(count / max) * 100}%` }}
              />
            </span>
            <span className="text-right text-sm text-ink-muted">{count.toLocaleString()}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function RecentFailures({ traces }: { traces: Trace[] }) {
  const failures = traces.filter((t) => !isHealthy(t.diagnosis.label)).slice(0, 7);
  if (failures.length === 0) {
    return <p className="px-5 pb-5 text-sm text-ink-muted">No failures among the latest traces.</p>;
  }
  return (
    <ul className="divide-y divide-line border-t border-line">
      {failures.map((trace) => (
        <li key={trace.traceId}>
          <Link
            href={`/dashboard/traces/${trace.traceId}`}
            className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-4 px-5 py-3 hover:bg-sunken"
          >
            <StageSequence trace={trace} />
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium">{trace.query.original}</span>
              <span className="mt-0.5 block text-xs text-ink-muted">{formatWhen(trace.timestamp)}</span>
            </span>
            <DiagnosisBadge label={trace.diagnosis.label} size="sm" />
          </Link>
        </li>
      ))}
    </ul>
  );
}

function Coverage({ summary }: { summary: TraceSummary | null }) {
  if (!summary || summary.total === 0) return null;
  const parts = [
    {
      key: "judge",
      name: "Final: LLM judge",
      swatch: "bg-current text-accent",
    },
    {
      key: "embedding",
      name: "Preliminary: embedding estimate",
      swatch: "hatch text-accent",
    },
    {
      key: "lexical",
      name: "Preliminary: term-overlap estimate",
      swatch: "hatch text-ink-muted",
    },
    {
      key: "unknown",
      name: "Not recorded (older traces)",
      swatch: "bg-current text-line",
    },
  ].map((p) => ({ ...p, count: summary.bySource[p.key] ?? 0 }));
  return (
    <div>
      <div className="flex h-3 overflow-hidden border border-line-strong" aria-hidden="true">
        {parts.map((p) => (
          <span key={p.key} className={`block ${p.swatch}`} style={{ width: `${(p.count / summary.total) * 100}%` }} />
        ))}
      </div>
      <ul className="mt-4 space-y-1.5 text-sm">
        {parts
          .filter((p) => p.count > 0)
          .map((p) => (
            <li key={p.key} className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-2">
                <span className={`block size-3 border border-line-strong ${p.swatch}`} aria-hidden="true" />
                {p.name}
              </span>
              <span className="text-ink-muted">{percent(p.count, summary.total)}</span>
            </li>
          ))}
      </ul>
      {(summary.bySource.judge ?? 0) === 0 && (
        <p className="mt-4 flex items-center gap-2 text-xs leading-5 text-ink-muted">
          <ProvenanceMark source="lexical" status={undefined} size="sm" />
          Without an LLM judge every diagnosis is an estimate; term overlap misses most paraphrased answers.
        </p>
      )}
    </div>
  );
}

function LatestExperiment({ run }: { run?: ExperimentEvalRun }) {
  if (!run) {
    return (
      <p className="text-sm leading-6 text-ink-muted">
        Compare pipeline settings on a labelled dataset with{" "}
        <code className="font-dash-mono text-[0.8125rem] text-ink">run_experiment</code>; results appear here.
      </p>
    );
  }
  const best = Math.max(...run.values.map((v) => v.healthyRate));
  return (
    <div>
      <p className="text-sm text-ink-muted">
        {run.experimentName}, comparing{" "}
        <code className="font-dash-mono text-[0.8125rem] text-ink">{run.comparedParameter}</code>
      </p>
      <ul className="mt-3 space-y-2 text-sm">
        {run.values.map((v) => (
          <li key={v.value} className="grid grid-cols-[6rem_1fr_4.5rem] items-center gap-3">
            <span
              className={`font-dash-mono text-[0.8125rem] ${v.healthyRate === best ? "font-medium" : "text-ink-muted"}`}
            >
              {v.value}
            </span>
            <span className="h-2 bg-sunken">
              <span
                className={`block h-2 ${v.healthyRate === best ? "bg-pass" : "bg-ink-muted/45"}`}
                style={{ width: `${v.healthyRate}%` }}
              />
            </span>
            <span className={`text-right ${v.healthyRate === best ? "font-semibold text-pass" : "text-ink-muted"}`}>
              {v.healthyRate}%
            </span>
          </li>
        ))}
      </ul>
      <Link href={`/dashboard/eval-runs/${run.id}`} className="mt-4 inline-block text-sm text-accent hover:underline">
        Open the experiment
      </Link>
    </div>
  );
}

// --- recovery --------------------------------------------------------------------

function getRecoveryInsights(runs: RecoveryRun[]) {
  const recovered = (r: RecoveryRun) => Boolean(r.finalDiagnosis && isHealthy(r.finalDiagnosis));
  return {
    runs: runs.length,
    recovered: runs.filter(recovered).length,
    retried: runs.filter((r) => r.attempts > 1).length,
    averageAttempts: runs.reduce((sum, r) => sum + r.attempts, 0) / runs.length,
    notable: runs.filter((r) => r.attempts > 1 || !recovered(r)).slice(0, 5),
    recoveredRun: recovered,
  };
}

function RecoveryInsights({ insights }: { insights: ReturnType<typeof getRecoveryInsights> }) {
  return (
    <div className="grid gap-6 md:grid-cols-[14rem_1fr]">
      <dl className="grid grid-cols-3 gap-4 md:grid-cols-1">
        <div>
          <dt className="text-sm text-ink-muted">Ended healthy</dt>
          <dd className="text-xl font-semibold">{percent(insights.recovered, insights.runs)}</dd>
        </div>
        <div>
          <dt className="text-sm text-ink-muted">Needed a retry</dt>
          <dd className="text-xl font-semibold">{insights.retried}</dd>
        </div>
        <div>
          <dt className="text-sm text-ink-muted">Attempts per run</dt>
          <dd className="text-xl font-semibold">{insights.averageAttempts.toFixed(1)}</dd>
        </div>
      </dl>
      {insights.notable.length === 0 ? (
        <p className="text-sm text-ink-muted">Every run was healthy on its first attempt.</p>
      ) : (
        <ul className="divide-y divide-line text-sm">
          {insights.notable.map((run) => (
            <li key={run.runId}>
              <Link
                href={`/dashboard/recovery-runs/${encodeURIComponent(run.runId)}`}
                className="block py-2.5 hover:bg-sunken"
              >
                <span className="block font-medium">{run.question}</span>
                <span className="mt-0.5 block text-ink-muted">
                  {insights.recoveredRun(run)
                    ? `Started as ${diagnosisName(run.firstDiagnosis ?? "").toLowerCase()}; healthy after ${run.attempts} attempts (${actionWords(run.actions[run.actions.length - 1])}).`
                    : `Still ${diagnosisName(run.finalDiagnosis ?? "").toLowerCase()} after ${run.attempts} attempts: the documents may not cover this.`}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
