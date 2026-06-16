import Link from "next/link";
import { notFound } from "next/navigation";

import { getTrace } from "@/lib/api";
import type { MockTrace, TraceDiagnosis } from "@/lib/mock-traces";

import { FeedbackWidget } from "./feedback-widget";

const diagnosisStyles: Record<TraceDiagnosis, string> = {
  healthy_answer: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  correct_refusal: "border-sky-500/30 bg-sky-500/10 text-sky-300",
  retrieval_miss: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  unsupported_claim: "border-red-500/30 bg-red-500/10 text-red-300",
  wrong_answer: "border-red-500/30 bg-red-500/10 text-red-300",
  low_context_relevance: "border-orange-500/30 bg-orange-500/10 text-orange-300",
  needs_review: "border-zinc-500/30 bg-zinc-500/10 text-zinc-300",
};

const deepLabelStyles: Record<string, string> = {
  grounded: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  not_grounded: "border-red-500/30 bg-red-500/10 text-red-300",
  needs_review: "border-zinc-500/30 bg-zinc-500/10 text-zinc-300",
  error: "border-amber-500/30 bg-amber-500/10 text-amber-300",
};

function deepLabelStyle(label: string) {
  return deepLabelStyles[label] ?? deepLabelStyles.needs_review;
}

function DeepRelevanceCard({
  title,
  label,
  reason,
}: {
  title: string;
  label: string;
  reason: string;
}) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-medium text-zinc-100">{title}</p>
        <span
          className={`shrink-0 rounded-md border px-2 py-1 text-xs font-medium ${
            label === "relevant"
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
              : "border-red-500/30 bg-red-500/10 text-red-300"
          }`}
        >
          {label}
        </span>
      </div>
      <p className="mt-2 text-sm leading-6 text-zinc-500">{reason}</p>
    </div>
  );
}

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

        <div className="flex items-center gap-2">
          {trace.status && (
            <span className="inline-flex rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm font-medium text-zinc-300">
              {formatLabel(trace.status)}
            </span>
          )}
          <span
            className={`inline-flex rounded-md border px-3 py-2 text-sm font-medium ${diagnosisStyles[trace.diagnosis.label]}`}
          >
            {formatLabel(trace.diagnosis.label)}
          </span>
        </div>
      </div>

      <div className="mt-8 grid gap-4 md:grid-cols-4">
        <MetricCard label="Model" value={trace.generation.model} />
        <MetricCard label="Total latency" value={`${trace.latency.totalMs}ms`} />
        {/* Show per-stage latency only when it was actually measured (> 0). */}
        {trace.latency.retrievalMs > 0 && (
          <MetricCard label="Retrieval" value={`${trace.latency.retrievalMs}ms`} />
        )}
        {trace.latency.generationMs > 0 && (
          <MetricCard label="Generation" value={`${trace.latency.generationMs}ms`} />
        )}
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

      {trace.evaluations.deepGroundedness && (
        <Panel title="Claim Support — LLM Judge" className="mt-6">
          <div className="flex items-center justify-between gap-4">
            <span
              className={`inline-flex rounded-md border px-3 py-1.5 text-sm font-medium ${deepLabelStyle(trace.evaluations.deepGroundedness.label)}`}
            >
              {formatLabel(trace.evaluations.deepGroundedness.label)}
            </span>
            {trace.evaluations.deepGroundedness.score !== null && (
              <span className="font-mono text-sm text-cyan-300">
                {Math.round(trace.evaluations.deepGroundedness.score * 100)}%
              </span>
            )}
          </div>

          <p className="mt-3 text-sm leading-6 text-zinc-400">
            {trace.evaluations.deepGroundedness.reason}
          </p>

          {(trace.evaluations.deepContextRelevance ||
            trace.evaluations.deepAnswerRelevance) && (
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {trace.evaluations.deepContextRelevance && (
                <DeepRelevanceCard
                  title="Context relevance"
                  label={trace.evaluations.deepContextRelevance.label}
                  reason={trace.evaluations.deepContextRelevance.reason}
                />
              )}
              {trace.evaluations.deepAnswerRelevance && (
                <DeepRelevanceCard
                  title="Answer relevance"
                  label={trace.evaluations.deepAnswerRelevance.label}
                  reason={trace.evaluations.deepAnswerRelevance.reason}
                />
              )}
            </div>
          )}

          {trace.evaluations.deepGroundedness.claims.length > 0 && (
            <div className="mt-5 space-y-3">
              {trace.evaluations.deepGroundedness.claims.map((claim, index) => (
                <div
                  key={index}
                  className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-4"
                >
                  <div className="flex items-start justify-between gap-4">
                    <p className="text-sm font-medium text-zinc-100">
                      {claim.claim}
                    </p>
                    <span
                      className={`shrink-0 rounded-md border px-2 py-1 text-xs font-medium ${
                        claim.supported
                          ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                          : "border-red-500/30 bg-red-500/10 text-red-300"
                      }`}
                    >
                      {claim.supported ? "supported" : "unsupported"}
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-zinc-500">
                    {claim.reason}
                  </p>
                </div>
              ))}
            </div>
          )}
        </Panel>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <Panel title="Retrieval Configuration">
          <div className="space-y-3">
            <Field label="Strategy" value={trace.retrieval.strategy} />
            {trace.retrieval.config && (
              <div className="grid grid-cols-2 gap-3">
                {trace.retrieval.config.lexicalTopK !== undefined && (
                  <Field label="Lexical top_k" value={String(trace.retrieval.config.lexicalTopK)} />
                )}
                {trace.retrieval.config.denseTopK !== undefined && (
                  <Field label="Dense top_k" value={String(trace.retrieval.config.denseTopK)} />
                )}
                {trace.retrieval.config.finalTopK !== undefined && (
                  <Field label="Final top_k" value={String(trace.retrieval.config.finalTopK)} />
                )}
                {trace.retrieval.config.fusion && (
                  <Field label="Fusion" value={trace.retrieval.config.fusion} />
                )}
                {trace.retrieval.config.reranker && (
                  <Field label="Reranker" value={trace.retrieval.config.reranker} />
                )}
              </div>
            )}
            {trace.latency.promptBuildMs !== undefined && (
              <Field label="Prompt build" value={`${trace.latency.promptBuildMs}ms`} />
            )}
          </div>
        </Panel>

        <Panel title="Prompt">
          {trace.prompt?.version && (
            <p className="mb-3 text-xs text-zinc-500">
              {trace.prompt.version}
              {trace.prompt.templateName ? ` / ${trace.prompt.templateName}` : ""}
            </p>
          )}
          {trace.prompt?.content ? (
            <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-md border border-zinc-800 bg-zinc-950/60 p-4 text-xs leading-6 text-zinc-400">
              {trace.prompt.content}
            </pre>
          ) : (
            <p className="text-sm text-zinc-500">No prompt was captured for this trace.</p>
          )}
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

                <span className="font-mono text-xs text-zinc-400">
                  final {chunk.score.toFixed(3)}
                </span>
              </div>

              <ChunkScores chunk={chunk} />

              <p className="mt-4 leading-7 text-zinc-400">{chunk.textPreview}</p>
            </div>
          ))}
        </div>
      </Panel>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1fr]">
        <Panel title="Add Feedback">
          <FeedbackWidget traceId={trace.traceId} />
        </Panel>

        <Panel title="Feedback">
          {trace.feedback && trace.feedback.length > 0 ? (
            <div className="space-y-3">
              {trace.feedback.map((item, index) => (
                <div
                  key={index}
                  className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-4"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium text-zinc-100">
                      {item.rating === "thumbs_up" ? "👍 Helpful" : "👎 Not helpful"}
                    </span>
                    {item.createdAt && (
                      <span className="text-xs text-zinc-500">
                        {new Date(item.createdAt).toLocaleString()}
                      </span>
                    )}
                  </div>
                  {item.comment && (
                    <p className="mt-2 text-sm leading-6 text-zinc-400">
                      {item.comment}
                    </p>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-zinc-500">No feedback yet.</p>
          )}
        </Panel>
      </div>
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

type Chunk = MockTrace["retrieval"]["chunks"][number];

function ChunkScores({ chunk }: { chunk: Chunk }) {
  const parts: string[] = [];
  if (chunk.rrfScore !== undefined) parts.push(`rrf ${chunk.rrfScore.toFixed(3)}`);
  if (chunk.lexicalScore !== undefined) parts.push(`lex ${chunk.lexicalScore.toFixed(3)}`);
  if (chunk.denseScore !== undefined) parts.push(`dense ${chunk.denseScore.toFixed(3)}`);
  if (chunk.lexicalRank !== undefined) parts.push(`lex#${chunk.lexicalRank}`);
  if (chunk.denseRank !== undefined) parts.push(`dense#${chunk.denseRank}`);

  if (parts.length === 0) {
    return null;
  }

  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {parts.map((part) => (
        <span
          key={part}
          className="rounded border border-zinc-800 bg-zinc-900/60 px-2 py-0.5 font-mono text-[11px] text-zinc-500"
        >
          {part}
        </span>
      ))}
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
