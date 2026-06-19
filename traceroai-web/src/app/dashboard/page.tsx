import Link from "next/link";

import { getEvalRuns, getJobStats, getTraces } from "@/lib/api";

// "Healthy" outcomes are not failures: a healthy answer AND a correct refusal
// (the model rightly declining when context lacks the answer) both count as good.
// Defined once so Healthy rate and Open failures stay consistent.
const HEALTHY_LABELS = new Set(["healthy_answer", "correct_refusal"]);

function calculateHealthyRate(traces: Awaited<ReturnType<typeof getTraces>>) {
  if (traces.length === 0) {
    return "--";
  }

  const healthyCount = traces.filter((trace) =>
    HEALTHY_LABELS.has(trace.diagnosis.label),
  ).length;

  return `${Math.round((healthyCount / traces.length) * 100)}%`;
}

// Only traces that actually reported latency (> 0) — a missing/unmeasured
// latency must NOT be counted as 0, or it skews the average and percentiles.
function measuredLatencies(traces: Awaited<ReturnType<typeof getTraces>>) {
  return traces
    .map((trace) => trace.latency.totalMs)
    .filter((ms) => ms > 0);
}

function calculateAverageLatency(traces: Awaited<ReturnType<typeof getTraces>>) {
  const values = measuredLatencies(traces);
  if (values.length === 0) {
    return "--";
  }
  const total = values.reduce((sum, ms) => sum + ms, 0);
  return `${Math.round(total / values.length)}ms`;
}

function calculatePercentileLatency(
  traces: Awaited<ReturnType<typeof getTraces>>,
  percentile: number,
) {
  const sorted = measuredLatencies(traces).sort((a, b) => a - b);
  if (sorted.length === 0) {
    return "--";
  }
  // Nearest-rank percentile.
  const rank = Math.ceil((percentile / 100) * sorted.length) - 1;
  const index = Math.min(Math.max(rank, 0), sorted.length - 1);
  return `${sorted[index]}ms`;
}

// Sum + average of per-trace cost, over traces that actually have a cost.
function calculateCost(traces: Awaited<ReturnType<typeof getTraces>>) {
  const costs = traces
    .map((t) => t.generation.costUsd)
    .filter((c): c is number => typeof c === "number" && c > 0);
  if (costs.length === 0) {
    return { total: "--", avg: "--" };
  }
  const total = costs.reduce((sum, c) => sum + c, 0);
  return {
    total: `$${total.toFixed(4)}`,
    avg: `$${(total / costs.length).toFixed(5)}`,
  };
}

// Map a "NN%" healthy-rate string to a status tone (>=80 good, >=50 warn, else bad).
function healthyRateTone(rate: string): "good" | "warn" | "bad" | undefined {
  const n = parseInt(rate, 10);
  if (Number.isNaN(n)) return undefined;
  return n >= 80 ? "good" : n >= 50 ? "warn" : "bad";
}

function calculateOpenFailures(traces: Awaited<ReturnType<typeof getTraces>>) {
  return traces.filter((trace) => !HEALTHY_LABELS.has(trace.diagnosis.label))
    .length;
}

export default async function DashboardPage() {
  const [traces, jobStats, evalRuns] = await Promise.all([
    getTraces(),
    getJobStats(),
    getEvalRuns(),
  ]);

  // Most recent experiment (eval-run harness output), if any.
  const latestExperiment = [...evalRuns.experimentRuns].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
  )[0];

  const totalTraces = traces.length;
  const healthyRate = calculateHealthyRate(traces);
  const averageLatency = calculateAverageLatency(traces);
  const p95Latency = calculatePercentileLatency(traces, 95);
  const openFailures = calculateOpenFailures(traces);
  const cost = calculateCost(traces);
  // Cost is shown only when (a) not disabled by env flag and (b) real cost data
  // exists. Per-project access control is a future concern (needs auth).
  const showCost =
    process.env.NEXT_PUBLIC_SHOW_COST !== "false" && cost.avg !== "--";

  return (
    <section>
      <div>
        <p className="text-sm font-medium uppercase tracking-[0.18em] text-cyan-300">
          Dashboard
        </p>
        <h1 className="mt-3 text-3xl font-semibold">RAG Reliability Overview</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-400">
          Monitor trace volume, failure patterns, evaluation quality, and latency
          across RAG pipeline runs.
        </p>
      </div>

      <div
        className={`mt-8 grid gap-4 md:grid-cols-3 ${
          showCost ? "lg:grid-cols-6" : "lg:grid-cols-5"
        }`}
      >
        <MetricCard label="Total traces" value={String(totalTraces)} />
        <MetricCard
          label="Healthy rate"
          value={healthyRate}
          tone={healthyRateTone(healthyRate)}
        />
        <MetricCard label="Avg latency" value={averageLatency} />
        <MetricCard label="p95 latency" value={p95Latency} />
        <MetricCard
          label="Open failures"
          value={String(openFailures)}
          tone={openFailures === 0 ? "good" : "bad"}
        />
        {showCost && <MetricCard label="Avg cost / trace" value={cost.avg} />}
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_1fr]">
        <section className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-6">
          <h2 className="text-lg font-semibold">Recent Traces</h2>
          <div className="mt-4 space-y-3">
            {traces.slice(0, 5).map((trace) => (
              <Link
                key={trace.traceId}
                href={`/dashboard/traces/${trace.traceId}`}
                className="block rounded-md border border-zinc-800 bg-zinc-950/60 p-4 transition hover:border-zinc-600 hover:bg-zinc-900/60"
              >
                <p className="line-clamp-1 text-sm font-medium">
                  {trace.query.original}
                </p>
                <p className="mt-2 text-xs text-zinc-500">
                  {trace.diagnosis.label.replaceAll("_", " ")} /{" "}
                  {trace.latency.totalMs}ms
                </p>
              </Link>
            ))}
            {traces.length === 0 && (
              <p className="text-sm text-zinc-600">No traces yet.</p>
            )}
          </div>
        </section>

        <div className="space-y-6">
          <section className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Deep-Eval Queue</h2>
              <span
                className={`inline-flex items-center gap-2 rounded-md border px-2.5 py-1 text-xs font-medium ${
                  jobStats.redisConnected
                    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                    : "border-zinc-600/40 bg-zinc-700/10 text-zinc-400"
                }`}
              >
                <span
                  className={`h-2 w-2 rounded-full ${
                    jobStats.redisConnected ? "bg-emerald-400" : "bg-zinc-500"
                  }`}
                />
                {jobStats.redisConnected ? "Redis connected" : "Fallback (in-process)"}
              </span>
            </div>
            <div className="mt-4 flex items-end gap-3">
              <p className="text-3xl font-semibold">{jobStats.queued}</p>
              <p className="pb-1 text-sm text-zinc-500">jobs queued</p>
            </div>
            <p className="mt-3 text-xs leading-5 text-zinc-500">
              {jobStats.redisConnected
                ? "Deep evaluations are processed asynchronously by the worker."
                : "Redis is not configured — deep evaluations run in-process via background tasks."}
            </p>
          </section>

          <section className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-6">
            <h2 className="text-lg font-semibold">Evaluation Methods</h2>
            <p className="mt-1 text-xs text-zinc-500">
              Share of traces touched by each evaluator (two-tier: fast quick pass
              + LLM-judge deep pass).
            </p>
            <div className="mt-4 space-y-3">
              {getEvalMethodMix(traces).map((item) => (
                <div key={item.label}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-zinc-300">{item.label}</span>
                    <span className="font-mono text-zinc-500">{item.percentage}%</span>
                  </div>
                  <div className="mt-2 h-2 rounded-full bg-zinc-800">
                    <div
                      className="h-2 rounded-full bg-violet-400"
                      style={{ width: `${item.percentage}%` }}
                    />
                  </div>
                </div>
              ))}
              {traces.length === 0 && (
                <p className="text-sm text-zinc-600">No traces yet.</p>
              )}
            </div>
          </section>

          <section className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-6">
            <h2 className="text-lg font-semibold">Failure Mix</h2>
            <div className="mt-4 space-y-3">
              {getFailureMix(traces).map((item) => (
                <Link
                  key={item.label}
                  href={`/dashboard/traces?diagnosis=${encodeURIComponent(item.label)}`}
                  className="group block rounded-md p-1 transition hover:bg-zinc-800/40"
                >
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-zinc-300 group-hover:text-zinc-100">
                      {item.label.replaceAll("_", " ")}
                    </span>
                    <span className="font-mono text-zinc-500">{item.count}</span>
                  </div>
                  <div className="mt-2 h-2 rounded-full bg-zinc-800">
                    <div
                      className="h-2 rounded-full bg-cyan-300"
                      style={{ width: `${item.percentage}%` }}
                    />
                  </div>
                </Link>
              ))}
              {traces.length === 0 && (
                <p className="text-sm text-zinc-600">No traces yet.</p>
              )}
            </div>
          </section>
        </div>
      </div>

      <section className="mt-6 rounded-lg border border-zinc-800 bg-zinc-900/60 p-6">
        {(() => {
          const g = getGroundednessDistribution(traces);
          return (
            <>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold">Groundedness</h2>
                  <p className="mt-1 text-xs text-zinc-500">
                    How well answers are supported by their retrieved context, across
                    evaluated traces.
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-3xl font-semibold text-emerald-300">{g.avg}%</p>
                  <p className="text-xs text-zinc-500">avg score</p>
                </div>
              </div>

              <div className="mt-4 flex items-center gap-2 text-xs text-zinc-400">
                <span className="rounded bg-emerald-500/10 px-2 py-1 text-emerald-300">
                  {g.groundedShare}% well grounded
                </span>
                <span className="text-zinc-600">·</span>
                <span>{g.evaluated} evaluated traces</span>
              </div>

              <div className="mt-6 flex items-end gap-3" style={{ height: "120px" }}>
                {g.bins.map((bin) => (
                  <div key={bin.range} className="flex flex-1 flex-col items-center justify-end">
                    <span className="mb-1 font-mono text-xs text-zinc-400">{bin.count}</span>
                    <div
                      className={`w-full rounded-t ${bin.tone}`}
                      style={{
                        height: `${bin.heightPct}%`,
                        minHeight: bin.count > 0 ? "4px" : "0",
                      }}
                    />
                    <span className="mt-2 font-mono text-[10px] text-zinc-600">{bin.range}</span>
                  </div>
                ))}
              </div>
              <div className="mt-2 flex justify-between text-[10px] uppercase tracking-wide text-zinc-600">
                <span>weak ←</span>
                <span>→ well grounded</span>
              </div>

              {g.evaluated === 0 && (
                <p className="mt-3 text-sm text-zinc-600">No evaluated traces yet.</p>
              )}
            </>
          );
        })()}
      </section>

      {latestExperiment && (
        <section className="mt-6 rounded-lg border border-zinc-800 bg-zinc-900/60 p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold">Latest Experiment</h2>
              <p className="mt-1 text-xs text-zinc-500">
                Pipeline configs compared on a labeled dataset, graded by an LLM judge.
              </p>
            </div>
            <Link
              href={`/dashboard/eval-runs/${latestExperiment.id}`}
              className="shrink-0 rounded-md border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-300 transition hover:border-zinc-500 hover:text-zinc-100"
            >
              View run →
            </Link>
          </div>

          <div className="mt-4 rounded-md border border-cyan-500/30 bg-cyan-500/10 p-3 text-sm text-cyan-200">
            <span className="font-medium">Recommended:</span>{" "}
            {latestExperiment.recommendation.reason}
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {(() => {
              // The winning variant is the highest accuracy (healthyRate). Computed
              // here rather than parsed from the recommendation text, so it's robust.
              const topRate = Math.max(
                ...latestExperiment.values.map((v) => v.healthyRate),
              );
              return latestExperiment.values.map((variant) => {
                const isWinner = variant.healthyRate === topRate;
                return (
                <div
                  key={variant.value}
                  className={`rounded-md border p-3 ${
                    isWinner
                      ? "border-cyan-500/40 bg-cyan-500/5"
                      : "border-zinc-800 bg-zinc-950/40"
                  }`}
                >
                  <p className="font-mono text-xs text-zinc-300">
                    {latestExperiment.comparedParameter} = {variant.value}
                  </p>
                  <p className="mt-2 text-2xl font-semibold">{variant.healthyRate}%</p>
                  <p className="text-xs text-zinc-500">
                    accuracy · {variant.avgLatencyMs}ms avg
                  </p>
                </div>
                );
              });
            })()}
          </div>
        </section>
      )}

      {(() => {
        const r = getRecoveryInsights(traces);
        if (!r) return null;
        return (
          <section className="mt-6 rounded-lg border border-zinc-800 bg-zinc-900/60 p-6">
            <h2 className="text-lg font-semibold">Self-healing recovery</h2>
            <p className="mt-1 text-xs text-zinc-500">
              How the RecoveryAgent is performing (grouped by question, judged on the
              final attempt) — use this to decide whether to raise default top_k,
              tighten prompts, or fill KB gaps.
            </p>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-md border border-zinc-800 bg-zinc-950/40 p-4">
                <p className="text-2xl font-semibold text-violet-300">{r.recoveredPct}%</p>
                <p className="text-xs text-zinc-500">ultimately recovered</p>
              </div>
              <div className="rounded-md border border-zinc-800 bg-zinc-950/40 p-4">
                <p className="text-2xl font-semibold">{r.avgAttempts}</p>
                <p className="text-xs text-zinc-500">avg attempts / question</p>
              </div>
              <div className="rounded-md border border-zinc-800 bg-zinc-950/40 p-4">
                <p className="text-2xl font-semibold">{r.retried}</p>
                <p className="text-xs text-zinc-500">needed a retry (&gt; 1 attempt)</p>
              </div>
              <div className="rounded-md border border-zinc-800 bg-zinc-950/40 p-4">
                <p className="text-2xl font-semibold">{r.runs}</p>
                <p className="text-xs text-zinc-500">
                  recovery runs ({r.attemptsTraced} attempts)
                </p>
              </div>
            </div>

            {r.suggestions.length > 0 ? (
              <div className="mt-4">
                <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                  What would improve these cases
                </p>
                <p className="mt-1 text-xs text-zinc-500">
                  {r.suggestions.length} of {r.runs} run(s) needed a fix; the rest
                  were healthy on the first attempt.
                </p>
                <ul className="mt-2 space-y-2">
                  {r.suggestions.map((s, i) => (
                    <li
                      key={i}
                      className="rounded-md border border-zinc-800 bg-zinc-950/40 p-3 text-sm"
                    >
                      <span className="text-zinc-300">“{s.question}”</span>
                      <span
                        className={`ml-2 ${
                          s.recovered ? "text-violet-300" : "text-amber-300"
                        }`}
                      >
                        → {s.recovered ? "recovered by: " : ""}
                        {s.fix}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="mt-4 rounded-md border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-sm text-emerald-300">
                ✓ No recovery action needed — answers were healthy on the first
                attempt. Per-case fixes appear here when the agent has to retry.
              </p>
            )}
          </section>
        );
      })()}
    </section>
  );
}

function MetricCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "good" | "warn" | "bad";
}) {
  const valueTone =
    tone === "good"
      ? "text-emerald-300"
      : tone === "warn"
        ? "text-amber-300"
        : tone === "bad"
          ? "text-red-300"
          : "text-zinc-100";
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-5 transition hover:border-zinc-700">
      <div className="flex items-center gap-2">
        {tone && (
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              tone === "good"
                ? "bg-emerald-400"
                : tone === "warn"
                  ? "bg-amber-400"
                  : "bg-red-400"
            }`}
          />
        )}
        <p className="text-sm text-zinc-500">{label}</p>
      </div>
      <p className={`mt-2 text-2xl font-semibold ${valueTone}`}>{value}</p>
    </div>
  );
}

// Bucket a 0..1 score into five bins for a distribution histogram. Only traces
// that were actually scored (> 0 OR an explicit evaluated label) are counted —
// "not_evaluated" traces are excluded so the histogram reflects real measurements.
const SCORE_BINS = ["0.0–0.2", "0.2–0.4", "0.4–0.6", "0.6–0.8", "0.8–1.0"];

// Per-bin color: low scores are a concern (red), high scores are good (emerald).
const BIN_TONES = [
  "bg-red-400/80",
  "bg-orange-400/80",
  "bg-amber-400/80",
  "bg-lime-400/80",
  "bg-emerald-400/80",
];

function getGroundednessDistribution(
  traces: Awaited<ReturnType<typeof getTraces>>,
) {
  const scores = traces
    .filter((t) => t.evaluations.groundedness.label !== "not_evaluated")
    .map((t) => t.evaluations.groundedness.score);

  const counts = [0, 0, 0, 0, 0];
  for (const s of scores) {
    // clamp into [0,1], then map to a bin index 0..4 (1.0 lands in the last bin)
    const clamped = Math.min(Math.max(s, 0), 1);
    const idx = Math.min(Math.floor(clamped * 5), 4);
    counts[idx] += 1;
  }
  const max = Math.max(1, ...counts);
  const evaluated = scores.length;
  const avg = evaluated
    ? Math.round((scores.reduce((a, b) => a + b, 0) / evaluated) * 100)
    : 0;
  // "Well grounded" = score >= 0.6 (top two bins).
  const wellGrounded = counts[3] + counts[4];
  const groundedShare = evaluated
    ? Math.round((wellGrounded / evaluated) * 100)
    : 0;

  const bins = SCORE_BINS.map((range, i) => ({
    range,
    count: counts[i],
    tone: BIN_TONES[i],
    heightPct: Math.round((counts[i] / max) * 100),
  }));
  return { bins, evaluated, avg, groundedShare };
}

// Share of traces each evaluation method touched. Surfaces the two-tier eval
// architecture (fast embedding/lexical quick pass + LLM-judge deep pass).
function getEvalMethodMix(traces: Awaited<ReturnType<typeof getTraces>>) {
  const total = traces.length;
  if (total === 0) {
    return [] as Array<{ label: string; count: number; percentage: number }>;
  }
  const count = (pred: (t: (typeof traces)[number]) => boolean) =>
    traces.filter(pred).length;

  const rows = [
    { label: "Embedding (semantic)", count: count((t) => !!t.evalMethods?.embedding) },
    { label: "Lexical (fallback)", count: count((t) => !!t.evalMethods?.lexical) },
    { label: "LLM judge (deep)", count: count((t) => !!t.evalMethods?.llmJudge) },
  ];
  return rows.map((r) => ({
    ...r,
    percentage: Math.round((r.count / total) * 100),
  }));
}

// Insight into the self-healing RecoveryAgent. Recovery sends ONE trace per
// attempt, so we group attempts into "runs" by question (the best proxy without a
// shared run-id) and judge each run by its FINAL (highest-attempt) outcome — so
// "recovered %" reflects whether the question was ultimately answered, not a raw
// per-attempt rate.
type RunInsight = {
  question: string;
  firstLabel: string;
  firstChunkCount: number;
  contextFailed: boolean;
  groundednessFailed: boolean;
  fixAction?: string;
};

// Describe the fix that recovered a run, grounded in what actually failed first.
function describeFix(r: RunInsight): string {
  if (r.fixAction === "bump_retrieval") {
    return `retrieval miss with ${r.firstChunkCount} chunk(s) — raising top_k surfaced the relevant context; consider top_k ≥ ${r.firstChunkCount + 2} or a better retriever`;
  }
  if (r.fixAction === "tighten_generation") {
    return "answer drifted from the context — a stricter grounding prompt fixed it; tighten your generation prompt to answer only from retrieved text";
  }
  // Recovered without a known lever (e.g. healthy on a re-retrieve): describe the cause.
  if (r.contextFailed) {
    return `retrieval was the weak point (${r.firstChunkCount} chunk(s)) — improve retrieval / raise top_k`;
  }
  if (r.groundednessFailed) {
    return "grounding was the weak point — tighten the prompt to stay on the context";
  }
  return `recovered from ${r.firstLabel.replaceAll("_", " ")} after a retry`;
}

// Describe a run that never reached a healthy answer — name the persistent failure.
function describeUnrecovered(r: RunInsight): string {
  if (r.firstLabel === "retrieval_miss" || r.contextFailed) {
    return `retrieval never surfaced the answer (${r.firstChunkCount} chunk(s)) — the docs likely don't cover this; add the missing content or improve indexing`;
  }
  if (r.firstLabel === "unsupported_claim" || r.groundednessFailed) {
    return "answer kept making unsupported claims — the context lacks the facts; add the missing docs";
  }
  return "never recovered — likely a knowledge-base gap; add the missing docs";
}

function getRecoveryInsights(traces: Awaited<ReturnType<typeof getTraces>>) {
  const recoveryTraces = traces.filter((t) => t.recovery);
  if (recoveryTraces.length === 0) {
    return null;
  }

  // Build per-question chains (all attempts, in order). Each chain = one run. We carry
  // the diagnosis, the lever taken, the chunk count, and the failing evaluator so we can
  // describe the ACTUAL cause — not a generic action label.
  const chains = new Map<
    string,
    Array<{
      attempt: number;
      label: string;
      action?: string;
      chunkCount: number;
      contextFailed: boolean;
      groundednessFailed: boolean;
    }>
  >();
  for (const t of recoveryTraces) {
    const key = t.query.original;
    if (!chains.has(key)) chains.set(key, []);
    chains.get(key)!.push({
      attempt: t.recovery!.attempt,
      label: t.diagnosis.label,
      action: t.recovery!.action,
      chunkCount: t.retrieval.chunks.length,
      contextFailed: t.evaluations.contextRelevance.label === "fail",
      groundednessFailed: t.evaluations.groundedness.label === "fail",
    });
  }

  const runList = [...chains.entries()].map(([question, atts]) => {
    const ordered = [...atts].sort((a, b) => a.attempt - b.attempt);
    const first = ordered[0];
    const final = ordered[ordered.length - 1];
    return {
      question,
      attempts: final.attempt,
      finalLabel: final.label,
      firstLabel: first.label, // what originally went wrong
      firstChunkCount: first.chunkCount,
      contextFailed: first.contextFailed,
      groundednessFailed: first.groundednessFailed,
      recovered: HEALTHY_LABELS.has(final.label),
      retried: ordered.length > 1,
      fixAction: final.action,
    };
  });

  const recovered = runList.filter((r) => r.recovered).length;
  const recoveredPct = Math.round((recovered / runList.length) * 100);
  const retried = runList.filter((r) => r.retried).length;
  const avgAttempts =
    runList.reduce((sum, r) => sum + r.attempts, 0) / runList.length;

  // Cause-specific suggestions — each names the ACTUAL failure (the first-attempt
  // diagnosis, chunk count, which evaluator failed) and the fix that the recovery
  // lever applied. No generic/fake text; all derived from the real retry chain.
  const suggestions: { question: string; fix: string; recovered: boolean }[] = [];
  for (const r of runList) {
    if (r.recovered && r.retried) {
      suggestions.push({
        question: r.question,
        fix: describeFix(r),
        recovered: true,
      });
    } else if (!r.recovered) {
      suggestions.push({
        question: r.question,
        fix: describeUnrecovered(r),
        recovered: false,
      });
    }
  }

  return {
    runs: runList.length,
    recoveredPct,
    avgAttempts: avgAttempts.toFixed(1),
    retried,
    attemptsTraced: recoveryTraces.length,
    suggestions,
  };
}

function getFailureMix(traces: Awaited<ReturnType<typeof getTraces>>) {
  const counts = new Map<string, number>();

  for (const trace of traces) {
    counts.set(
      trace.diagnosis.label,
      (counts.get(trace.diagnosis.label) || 0) + 1,
    );
  }

  return Array.from(counts.entries()).map(([label, count]) => ({
    label,
    count,
    percentage: traces.length === 0 ? 0 : Math.round((count / traces.length) * 100),
  }));
}