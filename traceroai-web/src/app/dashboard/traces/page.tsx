import Link from "next/link";

import { getTraces } from "@/lib/api";
import type { TraceDiagnosis } from "@/lib/mock-traces";

const diagnosisStyles: Record<TraceDiagnosis, string> = {
  healthy_answer: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  retrieval_miss: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  unsupported_claim: "border-red-500/30 bg-red-500/10 text-red-300",
  low_context_relevance: "border-orange-500/30 bg-orange-500/10 text-orange-300",
  needs_review: "border-zinc-500/30 bg-zinc-500/10 text-zinc-300",
};

function formatDiagnosis(label: string) {
  return label.replaceAll("_", " ");
}

function formatTime(timestamp: string) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(timestamp));
}

export default async function TracesPage() {
  const traces = await getTraces();
  return (
    <section>
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-cyan-300">
            Traces
          </p>
          <h1 className="mt-3 text-3xl font-semibold">RAG Trace Debugger</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-400">
            Inspect individual RAG requests and diagnose whether failures came
            from retrieval, context, prompting, or generation.
          </p>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 px-4 py-3">
          <p className="text-xs text-zinc-500">Total traces</p>
          <p className="mt-1 text-xl font-semibold">{traces.length}</p>
        </div>
      </div>

      <div className="mt-8 overflow-hidden rounded-lg border border-zinc-800">
        <div className="grid grid-cols-[1.4fr_160px_120px_120px_120px] border-b border-zinc-800 bg-zinc-950 px-4 py-3 text-xs font-medium uppercase tracking-wide text-zinc-500">
          <div>Query</div>
          <div>Diagnosis</div>
          <div>Model</div>
          <div>Latency</div>
          <div>Time</div>
        </div>

        <div className="divide-y divide-zinc-800">
          {traces.map((trace) => (
            <Link
              key={trace.traceId}
              href={`/dashboard/traces/${trace.traceId}`}
              className="grid grid-cols-[1.4fr_160px_120px_120px_120px] items-center bg-zinc-900/40 px-4 py-4 transition hover:bg-zinc-900"
            >
              <div>
                <p className="line-clamp-1 text-sm font-medium text-zinc-100">
                  {trace.query.original}
                </p>
                <p className="mt-1 line-clamp-1 text-xs text-zinc-500">
                  {trace.retrieval.strategy}
                </p>
              </div>

              <div>
                <span
                  className={`inline-flex rounded-md border px-2 py-1 text-xs font-medium ${diagnosisStyles[trace.diagnosis.label]}`}
                >
                  {formatDiagnosis(trace.diagnosis.label)}
                </span>
              </div>

              <div className="text-sm text-zinc-400">{trace.generation.model}</div>

              <div className="font-mono text-sm text-zinc-300">
                {trace.latency.totalMs}ms
              </div>

              <div className="text-sm text-zinc-500">
                {formatTime(trace.timestamp)}
              </div>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}