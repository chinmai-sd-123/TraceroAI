import Link from "next/link";
import { notFound } from "next/navigation";

import { getTrace } from "@/lib/api";
import type { TraceDiagnosis } from "@/lib/mock-traces";

const diagnosisStyles: Record<TraceDiagnosis, string> = {
  healthy_answer: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  retrieval_miss: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  unsupported_claim: "border-red-500/30 bg-red-500/10 text-red-300",
  low_context_relevance: "border-orange-500/30 bg-orange-500/10 text-orange-300",
  needs_review: "border-zinc-500/30 bg-zinc-500/10 text-zinc-300",
};

const relevanceStyles = {
  relevant: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  partially_relevant: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  irrelevant: "border-red-500/30 bg-red-500/10 text-red-300",
};

function formatLabel(label: string) {
  return label.replaceAll("_", " ");
}

export default async function TraceDetailPage({
  params,
}: {
  params: Promise<{ traceId: string }>;
}) {
  const { traceId } = await params;
  const trace = await getTrace(traceId);

  if (!trace) {
    notFound();
  }

  return (
    <section>
      <div className="mb-6">
        <Link
          href="/dashboard/traces"
          className="text-sm text-zinc-400 transition hover:text-zinc-100"
        >
          Back to traces
        </Link>
      </div>

      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-cyan-300">
            Trace Detail
          </p>
          <h1 className="mt-3 max-w-4xl text-3xl font-semibold leading-tight">
            {trace.query.original}
          </h1>
          <p className="mt-3 font-mono text-xs text-zinc-500">{trace.traceId}</p>
        </div>

        <span
          className={`inline-flex rounded-md border px-3 py-2 text-sm font-medium ${diagnosisStyles[trace.diagnosis.label]}`}
        >
          {formatLabel(trace.diagnosis.label)}
        </span>
      </div>

      <div className="mt-8 grid gap-4 md:grid-cols-4">
        <MetricCard label="Model" value={trace.generation.model} />
        <MetricCard label="Total latency" value={`${trace.latency.totalMs}ms`} />
        <MetricCard label="Retrieval" value={`${trace.latency.retrievalMs}ms`} />
        <MetricCard label="Generation" value={`${trace.latency.generationMs}ms`} />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <Panel title="Answer">
          <p className="leading-7 text-zinc-300">{trace.generation.answer}</p>
        </Panel>

        <Panel title="Diagnosis">
          <p className="text-sm font-medium text-zinc-100">
            {formatLabel(trace.diagnosis.label)}
          </p>
          <p className="mt-3 leading-7 text-zinc-400">{trace.diagnosis.reason}</p>
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <Panel title="Query Rewrite">
          <div className="space-y-4">
            <Field label="Original query" value={trace.query.original} />
            <Field
              label="Retrieval query"
              value={trace.query.rewritten || trace.query.original}
            />
          </div>
        </Panel>

        <Panel title="Evaluation">
          <div className="space-y-4">
            <EvalRow
              label="Groundedness"
              value={trace.evaluations.groundedness.label}
              score={trace.evaluations.groundedness.score}
              reason={trace.evaluations.groundedness.reason}
            />
            <EvalRow
              label="Context relevance"
              value={trace.evaluations.contextRelevance.label}
              score={trace.evaluations.contextRelevance.score}
              reason={trace.evaluations.contextRelevance.reason}
            />
            <EvalRow
              label="Answer relevance"
              value={trace.evaluations.answerRelevance.label}
              score={trace.evaluations.answerRelevance.score}
              reason={trace.evaluations.answerRelevance.reason}
            />
          </div>
        </Panel>
      </div>

      <Panel title="Retrieved Chunks" className="mt-6">
        <div className="space-y-4">
          {trace.retrieval.chunks.map((chunk) => (
            <div
              key={chunk.chunkId}
              className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-4"
            >
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <p className="text-sm font-semibold text-zinc-100">
                    #{chunk.rank} {chunk.documentTitle}
                  </p>
                  <p className="mt-1 text-xs text-zinc-500">
                    {chunk.section} / {chunk.source}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <span
                    className={`rounded-md border px-2 py-1 text-xs font-medium ${relevanceStyles[chunk.relevance]}`}
                  >
                    {formatLabel(chunk.relevance)}
                  </span>
                  <span className="font-mono text-xs text-zinc-500">
                    score {chunk.score}
                  </span>
                </div>
              </div>

              <p className="mt-4 leading-7 text-zinc-400">{chunk.textPreview}</p>
            </div>
          ))}
        </div>
      </Panel>
    </section>
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
    <div>
      <p className="text-xs uppercase tracking-wide text-zinc-500">{label}</p>
      <p className="mt-2 text-sm leading-6 text-zinc-300">{value}</p>
    </div>
  );
}

function EvalRow({
  label,
  value,
  score,
  reason,
}: {
  label: string;
  value: string;
  score: number;
  reason: string;
}) {
  return (
    <div className="border-b border-zinc-800 pb-4 last:border-b-0 last:pb-0">
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm font-medium text-zinc-100">{label}</p>
        <p className="font-mono text-sm text-cyan-300">{Math.round(score * 100)}%</p>
      </div>
      <p className="mt-1 text-sm text-zinc-400">{formatLabel(value)}</p>
      <p className="mt-2 text-sm leading-6 text-zinc-500">{reason}</p>
    </div>
  );
}
