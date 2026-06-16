import { getJobStats, getTraces } from "@/lib/api";

function calculateHealthyRate(traces: Awaited<ReturnType<typeof getTraces>>) {
  if (traces.length === 0) {
    return "--";
  }

  const healthyCount = traces.filter(
    (trace) => trace.diagnosis.label === "healthy_answer",
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

// "Healthy" outcomes are not failures: a healthy answer AND a correct refusal
// (the model rightly declining when context lacks the answer) both count as good.
const HEALTHY_LABELS = new Set(["healthy_answer", "correct_refusal"]);

function calculateOpenFailures(traces: Awaited<ReturnType<typeof getTraces>>) {
  return traces.filter((trace) => !HEALTHY_LABELS.has(trace.diagnosis.label))
    .length;
}

export default async function DashboardPage() {
  const [traces, jobStats] = await Promise.all([getTraces(), getJobStats()]);

  const totalTraces = traces.length;
  const healthyRate = calculateHealthyRate(traces);
  const averageLatency = calculateAverageLatency(traces);
  const p95Latency = calculatePercentileLatency(traces, 95);
  const openFailures = calculateOpenFailures(traces);

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

      <div className="mt-8 grid gap-4 md:grid-cols-5">
        <MetricCard label="Total traces" value={String(totalTraces)} />
        <MetricCard label="Healthy rate" value={healthyRate} />
        <MetricCard label="Avg latency" value={averageLatency} />
        <MetricCard label="p95 latency" value={p95Latency} />
        <MetricCard label="Open failures" value={String(openFailures)} />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_1fr]">
        <section className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-6">
          <h2 className="text-lg font-semibold">Recent Traces</h2>
          <div className="mt-4 space-y-3">
            {traces.slice(0, 5).map((trace) => (
              <div
                key={trace.traceId}
                className="rounded-md border border-zinc-800 bg-zinc-950/60 p-4"
              >
                <p className="line-clamp-1 text-sm font-medium">
                  {trace.query.original}
                </p>
                <p className="mt-2 text-xs text-zinc-500">
                  {trace.diagnosis.label.replaceAll("_", " ")} /{" "}
                  {trace.latency.totalMs}ms
                </p>
              </div>
            ))}
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
            <h2 className="text-lg font-semibold">Failure Mix</h2>
            <div className="mt-4 space-y-3">
              {getFailureMix(traces).map((item) => (
                <div key={item.label}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-zinc-300">
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
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-5">
      <p className="text-sm text-zinc-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </div>
  );
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