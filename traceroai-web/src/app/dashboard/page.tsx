import { getTraces } from "@/lib/api";

function calculateHealthyRate(traces: Awaited<ReturnType<typeof getTraces>>) {
  if (traces.length === 0) {
    return "--";
  }

  const healthyCount = traces.filter(
    (trace) => trace.diagnosis.label === "healthy_answer",
  ).length;

  return `${Math.round((healthyCount / traces.length) * 100)}%`;
}

function calculateAverageLatency(traces: Awaited<ReturnType<typeof getTraces>>) {
  if (traces.length === 0) {
    return "--";
  }

  const totalLatency = traces.reduce(
    (sum, trace) => sum + trace.latency.totalMs,
    0,
  );

  return `${Math.round(totalLatency / traces.length)}ms`;
}

function calculateOpenFailures(traces: Awaited<ReturnType<typeof getTraces>>) {
  return traces.filter((trace) => trace.diagnosis.label !== "healthy_answer")
    .length;
}

export default async function DashboardPage() {
  const traces = await getTraces();

  const totalTraces = traces.length;
  const healthyRate = calculateHealthyRate(traces);
  const averageLatency = calculateAverageLatency(traces);
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

      <div className="mt-8 grid gap-4 md:grid-cols-4">
        <MetricCard label="Total traces" value={String(totalTraces)} />
        <MetricCard label="Healthy rate" value={healthyRate} />
        <MetricCard label="Avg latency" value={averageLatency} />
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