import { cookies } from "next/headers";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { CSSProperties } from "react";
import type { ReactNode } from "react";

import { provenanceSentence } from "@/components/diagnosis-provenance";
import { getTrace, getTraces, parseRange, rangeSince } from "@/lib/api";
import { LAYOUT_COOKIE, clampWidth, parseLayout } from "@/lib/layout-prefs";
import type { Trace } from "@/lib/trace-types";

import { CopyButton } from "@/components/copy-button";
import { ArrowLeftIcon, CheckIcon, CrossIcon, ThumbDownIcon, ThumbUpIcon } from "@/components/icons";
import { ListKeys } from "../../list-keys";
import {
  ProvenanceMark,
  STATE_WORDS,
  type Stage,
  type StageKey,
  StageDocket,
  StageMark,
  TONE_TEXT,
  causeStage,
  diagnosisName,
  diagnosisTone,
  formatCost,
  formatMs,
  formatWhen,
  hrefWith,
  stagesOf,
} from "../../ui";
import { TraceRailList, listHref, parseDiagnosis, parseSort, type TraceListFilters } from "../trace-list";
import { FeedbackWidget } from "./feedback-widget";
import { RecoveryStrip } from "./recovery-strip";
import { Splitter } from "../../splitter";

// The trace page: what happened (the question and verdict), the findings for
// each pipeline stage, then the execution itself, step by step. Selecting a
// step shows its inputs, outputs and the check that judged it.

const STEPS = ["query", "retrieval", "prompt", "generation", "evaluation", "feedback", "json"] as const;
type Step = (typeof STEPS)[number];

// The step where each stage's evidence lives.
const STAGE_STEP: Record<StageKey, Step> = {
  retrieval: "retrieval",
  grounding: "generation",
  answer: "generation",
};

const STEP_NAMES: Record<Step, string> = {
  query: "Query",
  retrieval: "Retrieval",
  prompt: "Prompt",
  generation: "Generation",
  evaluation: "Evaluation",
  feedback: "Feedback",
  json: "Raw trace",
};

export default async function TraceDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ traceId: string }>;
  searchParams: Promise<{
    project?: string;
    diagnosis?: string;
    q?: string;
    range?: string;
    model?: string;
    environment?: string;
    sort?: string;
    step?: string;
  }>;
}) {
  const { traceId } = await params;
  const sp = await searchParams;
  const range = parseRange(sp.range, "all");
  const filters: TraceListFilters = {
    project: sp.project,
    diagnosis: parseDiagnosis(sp.diagnosis),
    q: sp.q?.trim() || undefined,
    range: range === "all" ? undefined : range,
    model: sp.model || undefined,
    environment: sp.environment || undefined,
    sort: parseSort(sp.sort),
  };

  const [trace, list, cookieStore] = await Promise.all([
    getTrace(traceId),
    getTraces({
      projectId: filters.project,
      diagnosis: filters.diagnosis,
      q: filters.q,
      model: filters.model,
      environment: filters.environment,
      sort: filters.sort,
      since: rangeSince(range),
      limit: 50,
    }),
    cookies(),
  ]);
  if (!trace) notFound();

  // Column widths the viewer dragged to, so the server draws them at that size.
  const widths = parseLayout(cookieStore.get(LAYOUT_COOKIE)?.value).widths ?? {};
  const listWidth = clampWidth("traceList", widths.traceList);
  const timelineWidth = clampWidth("timeline", widths.timeline);

  const cause = causeStage(trace.diagnosis.label);
  // Open on the step that holds the evidence for what broke.
  const defaultStep: Step = cause
    ? STAGE_STEP[cause]
    : trace.diagnosis.label === "needs_review"
      ? "evaluation"
      : "generation";
  const step: Step = STEPS.includes(sp.step as Step) ? (sp.step as Step) : defaultStep;
  const stepHref = (key: Step) =>
    hrefWith(`/dashboard/traces/${encodeURIComponent(trace.traceId)}`, {
      ...filters,
      step: key === defaultStep ? undefined : key,
    }) + "#execution";

  const tone = diagnosisTone(trace.diagnosis.label);
  const note =
    trace.diagnosis.source === "judge" && trace.deepStatus !== "partial"
      ? null
      : provenanceSentence(trace.diagnosis.source, trace.deepStatus);
  const cost = process.env.NEXT_PUBLIC_SHOW_COST !== "false" ? formatCost(trace.generation.costUsd) : null;
  const stages = stagesOf(trace);

  return (
    <div
      data-resize-root
      style={{ "--col-traceList": `${listWidth}px`, "--col-timeline": `${timelineWidth}px` } as CSSProperties}
      className="lg:grid lg:grid-cols-[var(--col-traceList)_minmax(0,1fr)]"
    >
      <ListKeys mode="navigate" />
      <aside aria-label="Trace list" className="relative hidden border-r border-line bg-sunken lg:sticky lg:top-0 lg:block lg:h-screen">
        <TraceRailList traces={list.traces} selected={trace.traceId} filters={filters} />
        <Splitter id="traceList" label="Resize the trace list" initial={listWidth} />
      </aside>

      <article className="min-w-0 px-4 py-6 sm:px-8 lg:px-10 lg:py-8">
        <div className="max-w-[68rem]">
          <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-sm text-ink-muted">
            <Link href={listHref(filters)} className="inline-flex items-center gap-1.5 hover:text-ink hover:underline">
              <ArrowLeftIcon className="lg:hidden" />
              Traces
            </Link>
            <span aria-hidden="true" className="text-line-strong">/</span>
            <span aria-current="page" className="truncate font-dash-mono text-xs">{trace.traceId}</span>
          </nav>

          <h1 className="mt-2 text-2xl font-semibold tracking-[-0.015em] text-balance">{trace.query.original}</h1>

          <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-line pb-4 text-sm text-ink-muted">
          <dl className="flex flex-wrap items-center gap-x-5 gap-y-2">
            <Meta label="Model">{trace.generation.model}</Meta>
            <Meta label="Latency">{formatMs(trace.latency.totalMs)}</Meta>
            {trace.generation.totalTokens ? <Meta label="Tokens">{trace.generation.totalTokens.toLocaleString()}</Meta> : null}
            {cost && <Meta label="Cost">{cost}</Meta>}
            <Meta label="Received">
              <time dateTime={trace.timestamp}>
                {new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(trace.timestamp))}
              </time>
            </Meta>
          </dl>
            <div className="ml-auto">
              <CopyButton text={trace.traceId} label="Copy trace id" />
            </div>
          </div>

          {trace.recovery && <RecoveryStrip trace={trace} />}

          <section aria-labelledby="verdict" className="mt-6">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-2">
              <span className="text-sm text-ink-muted">{cause ? "Probable cause" : "Diagnosis"}</span>
              <strong id="verdict" className={`text-xl font-semibold ${TONE_TEXT[tone]}`}>
                {diagnosisName(trace.diagnosis.label)}
              </strong>
              <ProvenanceMark source={trace.diagnosis.source} status={trace.deepStatus} />
            </div>
            <p className="mt-1.5 max-w-[70ch] text-[15px] leading-7 text-pretty">{trace.diagnosis.reason}</p>
            {note && <p className="mt-1 max-w-[70ch] text-sm text-ink-muted">{note}</p>}
          </section>

          <section aria-labelledby="findings-heading" className="mt-5">
            <h2 id="findings-heading" className="sr-only">
              Findings by stage
            </h2>
            <StageDocket trace={trace} inspectHref={(stage) => stepHref(STAGE_STEP[stage])} />
          </section>

          <section id="execution" aria-labelledby="execution-heading" className="mt-10 scroll-mt-6">
            <h2 id="execution-heading" className="font-semibold">Execution</h2>
            <p className="mt-0.5 text-sm text-ink-muted">
              Each step in order, drawn to time where the SDK measured it. Select a step to see what went in and
              what came out.
            </p>
            <div className="mt-4 grid items-start gap-6 xl:grid-cols-[var(--col-timeline)_minmax(0,1fr)]">
              <div className="relative min-w-0">
                <ExecutionTimeline trace={trace} stages={stages} active={step} stepHref={stepHref} />
                <Splitter id="timeline" label="Resize the timeline" initial={timelineWidth} className="-right-[18px] xl:block" />
              </div>
              <section aria-label={`${STEP_NAMES[step]} details`} className="min-w-0 rounded border border-line">
                <div className="border-b border-line bg-sunken px-5 py-3">
                  <h3 className="font-semibold">{STEP_NAMES[step]}</h3>
                </div>
                <div className="px-5 py-5">
                  {step === "query" && <QueryPanel trace={trace} />}
                  {step === "retrieval" && <RetrievalPanel trace={trace} stages={stages} />}
                  {step === "prompt" && <PromptTab trace={trace} />}
                  {step === "generation" && <GenerationPanel trace={trace} stages={stages} />}
                  {step === "evaluation" && <EvaluationPanel trace={trace} />}
                  {step === "feedback" && <FeedbackTab trace={trace} />}
                  {step === "json" && <JsonTab trace={trace} />}
                </div>
              </section>
            </div>
          </section>
        </div>
      </article>
    </div>
  );
}

function Meta({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <dt>{label}</dt>
      <dd className="text-ink">{children}</dd>
    </div>
  );
}

// --- execution timeline ------------------------------------------------------------

/** The pipeline's steps as a waterfall: each timed step's bar starts where the
 * previous one ended, scaled to the trace's total latency. Untimed steps say
 * so instead of drawing a guess. */
function ExecutionTimeline({
  trace,
  stages,
  active,
  stepHref,
}: {
  trace: Trace;
  stages: Stage[];
  active: Step;
  stepHref: (step: Step) => string;
}) {
  const timed = {
    retrieval: trace.latency.retrievalMs,
    prompt: trace.latency.promptBuildMs ?? 0,
    generation: trace.latency.generationMs,
  };
  const sum = timed.retrieval + timed.prompt + timed.generation;
  const scale = Math.max(trace.latency.totalMs, sum);
  const byKey = Object.fromEntries(stages.map((s) => [s.key, s])) as Record<StageKey, Stage>;
  const judge =
    trace.deepStatus === "pending"
      ? "judge pending"
      : trace.deepStatus === "failed"
        ? "judge failed"
        : trace.deepStatus === "skipped"
          ? "estimate only, no judge"
          : trace.diagnosis.source === "judge"
            ? "decided by the LLM judge"
            : "estimate";

  const rows: Array<{ step: Step; detail: string; ms?: number; marks?: Stage[] }> = [
    {
      step: "query",
      detail:
        trace.query.rewritten && trace.query.rewritten !== trace.query.original ? "rewritten for search" : "as asked",
    },
    {
      step: "retrieval",
      detail: `${trace.retrieval.chunks.length} chunk${trace.retrieval.chunks.length === 1 ? "" : "s"}`,
      ms: timed.retrieval,
      marks: [byKey.retrieval],
    },
    {
      step: "prompt",
      detail: trace.prompt?.content ? trace.prompt.templateName || "captured" : "not captured",
      ms: timed.prompt,
    },
    { step: "generation", detail: trace.generation.model, ms: timed.generation, marks: [byKey.grounding, byKey.answer] },
    { step: "evaluation", detail: judge },
  ];

  // Waterfall positions: each timed step starts where the previous ended.
  let offset = 0;
  const positions = rows.map((row) => {
    if (!row.ms || row.ms <= 0 || scale <= 0) return null;
    const position = { left: (offset / scale) * 100, width: Math.max(1, (row.ms / scale) * 100) };
    offset += row.ms;
    return position;
  });

  return (
    <nav aria-label="Execution steps" className="rounded border border-line">
      <ol>
        {rows.map((row, i) => {
          const position = positions[i];
          const on = row.step === active;
          return (
            <li key={row.step} className="border-b border-line last:border-b-0">
              <Link
                href={stepHref(row.step)}
                scroll={false}
                aria-current={on ? "step" : undefined}
                className={`grid grid-cols-[7.5rem_minmax(0,1fr)_4.25rem] items-center gap-3 px-4 py-2.5 text-sm focus-visible:-outline-offset-2 ${
                  on ? "bg-accent-soft" : "hover:bg-sunken"
                }`}
              >
                <span className="min-w-0">
                  <span className={`flex items-center gap-1.5 ${on ? "font-semibold" : "font-medium"}`}>
                    {STEP_NAMES[row.step]}
                    {row.marks?.map((m) => <StageMark key={m.key} stage={m} />)}
                  </span>
                  <span className="block truncate text-xs text-ink-muted">{row.detail}</span>
                </span>
                <span className="relative h-2" aria-hidden="true">
                  {row.ms !== undefined && <span className="absolute inset-x-0 top-1/2 border-t border-dashed border-line" />}
                  {position && (
                    <span
                      className={`absolute inset-y-0 ${row.step === "generation" ? "bg-ink-muted/60" : "bg-accent"}`}
                      style={{ left: `${position.left}%`, width: `${position.width}%` }}
                    />
                  )}
                </span>
                <span className="text-right text-xs whitespace-nowrap text-ink-muted">
                  {row.ms === undefined ? "" : row.ms > 0 ? formatMs(row.ms) : "not timed"}
                </span>
              </Link>
            </li>
          );
        })}
      </ol>
      <ul className="border-t border-line-strong bg-sunken">
        {(["feedback", "json"] as const).map((key) => (
          <li key={key} className="border-b border-line last:border-b-0">
            <Link
              href={stepHref(key)}
              scroll={false}
              aria-current={key === active ? "step" : undefined}
              className={`flex justify-between px-4 py-2 text-sm focus-visible:-outline-offset-2 ${
                key === active ? "bg-accent-soft font-semibold" : "text-ink-muted hover:text-ink"
              }`}
            >
              {STEP_NAMES[key]}
              {key === "feedback" && trace.feedback?.length ? (
                <span className="text-xs text-ink-muted">{trace.feedback.length}</span>
              ) : null}
            </Link>
          </li>
        ))}
      </ul>
      {scale > 0 && (
        <p className="border-t border-line px-4 py-2 text-xs text-ink-muted">
          Total {formatMs(trace.latency.totalMs || sum)}
          {trace.latency.totalMs > sum && sum > 0
            ? `; ${formatMs(trace.latency.totalMs - sum)} outside the timed steps`
            : ""}
        </p>
      )}
    </nav>
  );
}

// --- step panels ---------------------------------------------------------------------

function PanelSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-6 first:mt-0">
      <h4 className="mb-2 text-xs font-semibold text-ink-muted">{title}</h4>
      {children}
    </section>
  );
}

/** A stage's verdict as its check found it: state, reason, and who decided. */
function StageCheck({ stage }: { stage: Stage }) {
  return (
    <div className={`rounded border px-4 py-3 ${stage.cause ? "border-cause/40 bg-cause-soft" : "border-line"}`}>
      <p className="flex flex-wrap items-center gap-2 text-sm">
        <StageMark stage={stage} />
        <span className="font-semibold">{stage.name}</span>
        <span
          className={`font-semibold ${
            stage.cause ? "text-cause" : stage.state === "pass" ? "text-pass" : stage.state === "review" ? "text-warn" : ""
          }`}
        >
          {STATE_WORDS[stage.state]}
        </span>
        {stage.cause && <span className="text-xs font-semibold text-cause">Probable cause</span>}
      </p>
      <p className="mt-1 text-sm text-ink-muted">{stage.question}</p>
      {stage.reason && <p className="mt-2 max-w-[70ch] text-sm leading-6">{stage.reason}</p>}
      <p className="mt-2 text-xs text-ink-muted">
        {stage.state === "unknown"
          ? "No check ran on this stage."
          : stage.judged
            ? "Final: decided by the LLM judge."
            : `Preliminary: estimated from ${stage.method}.`}
        {stage.overruled && (
          <>
            {" "}
            <s>
              The estimate ({stage.overruled.method}) said {STATE_WORDS[stage.overruled.state].toLowerCase()}.
            </s>
            <span className="sr-only"> The judge overruled it.</span>
          </>
        )}
      </p>
    </div>
  );
}

function QueryPanel({ trace }: { trace: Trace }) {
  const rewritten =
    trace.query.rewritten && trace.query.rewritten !== trace.query.original ? trace.query.rewritten : null;
  return (
    <>
      <PanelSection title="Asked">
        <p className="max-w-[70ch] text-[15px] leading-7">{trace.query.original}</p>
      </PanelSection>
      <PanelSection title="Sent to the retriever">
        <p className="max-w-[70ch] text-[15px] leading-7">
          {rewritten ?? <span className="text-ink-muted">The question as asked.</span>}
        </p>
      </PanelSection>
    </>
  );
}

function RetrievalPanel({ trace, stages }: { trace: Trace; stages: Stage[] }) {
  return (
    <>
      <PanelSection title="Check">
        <StageCheck stage={stages[0]} />
      </PanelSection>
      <PanelSection title="Input and output">
        <ChunksTab trace={trace} />
      </PanelSection>
    </>
  );
}

function GenerationPanel({ trace, stages }: { trace: Trace; stages: Stage[] }) {
  return (
    <>
      <PanelSection title="Checks">
        <div className="grid gap-3">
          <StageCheck stage={stages[1]} />
          <StageCheck stage={stages[2]} />
        </div>
      </PanelSection>
      <PanelSection title="Output">
        <AnswerTab trace={trace} />
      </PanelSection>
    </>
  );
}

async function EvaluationPanel({ trace }: { trace: Trace }) {
  // Other traces of the same question, to see whether this failure is new.
  const related = await getTraces({ q: trace.query.original.slice(0, 200), limit: 8 });
  const history = related.traces
    .filter((t) => t.traceId !== trace.traceId && t.query.original === trace.query.original)
    .slice(0, 5);
  return (
    <>
      <EvaluationTab trace={trace} />
      <PanelSection title="Same question, other traces">
        {history.length === 0 ? (
          <p className="text-sm text-ink-muted">No other trace asked exactly this question.</p>
        ) : (
          <ul className="divide-y divide-line border-y border-line text-sm">
            {history.map((t) => (
              <li key={t.traceId}>
                <Link href={`/dashboard/traces/${t.traceId}`} className="flex items-center gap-3 px-1 py-2 hover:bg-sunken">
                  <span className="font-dash-mono text-xs text-ink-muted">{t.traceId.slice(0, 8)}</span>
                  <span className="font-medium">{diagnosisName(t.diagnosis.label)}</span>
                  <span className="text-ink-muted">{t.generation.model}</span>
                  <span className="ml-auto text-xs text-ink-muted">{formatWhen(t.timestamp)}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </PanelSection>
    </>
  );
}

// --- evidence bodies, shared by the step panels -------------------------------------

function ChunksTab({ trace }: { trace: Trace }) {
  const { retrieval, query } = trace;
  const rewritten = query.rewritten && query.rewritten !== query.original ? query.rewritten : null;
  const config = retrieval.config
    ? Object.entries({
        "lexical top_k": retrieval.config.lexicalTopK,
        "dense top_k": retrieval.config.denseTopK,
        "final top_k": retrieval.config.finalTopK,
        fusion: retrieval.config.fusion,
        reranker: retrieval.config.reranker,
      }).filter(([, v]) => v !== undefined && v !== "")
    : [];
  return (
    <div>
      <dl className="mb-4 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
        {rewritten && (
          <>
            <dt className="text-ink-muted">Searched for</dt>
            <dd>{rewritten}</dd>
          </>
        )}
        <dt className="text-ink-muted">Strategy</dt>
        <dd className="font-dash-mono text-[0.8125rem]">
          {retrieval.strategy}
          {config.map(([k, v]) => (
            <span key={k} className="ml-3 text-ink-muted">
              {k} {String(v)}
            </span>
          ))}
        </dd>
      </dl>
      {retrieval.chunks.length === 0 ? (
        <p className="text-sm text-ink-muted">Nothing was retrieved for this question.</p>
      ) : (
        <ol className="divide-y divide-line border-y border-line">
          {retrieval.chunks.map((chunk) => (
            <li key={`${chunk.rank}-${chunk.chunkId}`} className="grid gap-x-4 py-4 sm:grid-cols-[2rem_minmax(0,1fr)_auto]">
              <span className="text-sm text-ink-muted">{chunk.rank}</span>
              <div className="min-w-0">
                <p className="font-medium">
                  {chunk.documentTitle}
                  {chunk.section && chunk.section !== chunk.documentTitle && (
                    <span className="font-normal text-ink-muted"> · {chunk.section}</span>
                  )}
                </p>
                {chunk.source && chunk.source !== chunk.documentTitle && (
                  <p className="mt-0.5 truncate font-dash-mono text-xs text-ink-muted">{chunk.source}</p>
                )}
                <p className="mt-2 max-w-[75ch] text-sm leading-6 text-pretty whitespace-pre-line">{chunk.textPreview}</p>
              </div>
              <ChunkScore chunk={chunk} />
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

type Chunk = Trace["retrieval"]["chunks"][number];

function ChunkScore({ chunk }: { chunk: Chunk }) {
  const extra = [
    chunk.rrfScore !== undefined && `rrf ${chunk.rrfScore.toFixed(3)}`,
    chunk.lexicalScore !== undefined && `lexical ${chunk.lexicalScore.toFixed(3)}`,
    chunk.denseScore !== undefined && `dense ${chunk.denseScore.toFixed(3)}`,
    chunk.lexicalRank !== undefined && `lexical #${chunk.lexicalRank}`,
    chunk.denseRank !== undefined && `dense #${chunk.denseRank}`,
  ].filter(Boolean) as string[];
  return (
    <div className="mt-2 text-right font-dash-mono text-[0.8125rem] sm:mt-0">
      {chunk.score != null ? (
        <p title="Score from your retriever">{chunk.score.toFixed(3)}</p>
      ) : (
        <p className="text-xs text-ink-muted">No score</p>
      )}
      {extra.map((e) => (
        <p key={e} className="text-xs text-ink-muted">{e}</p>
      ))}
    </div>
  );
}

function AnswerTab({ trace }: { trace: Trace }) {
  const deep = trace.evaluations.deepGroundedness;
  const blamed = causeStage(trace.diagnosis.label) === "grounding";
  const g = trace.generation;
  const params = [
    g.provider && ["Provider", g.provider],
    typeof g.temperature === "number" && ["Temperature", String(g.temperature)],
    ...Object.entries(g.parameters ?? {}).map(([k, v]) => [k.replaceAll("_", " "), String(v)]),
  ].filter(Boolean) as Array<[string, string]>;
  return (
    <div className="space-y-8">
      <blockquote className="max-w-[75ch] border-l border-line-strong pl-4 text-[15px] leading-7 whitespace-pre-line">
        {g.answer || <span className="text-ink-muted">No answer was recorded.</span>}
      </blockquote>

      {deep && deep.claims.length > 0 && (
        <section>
          <h2 className="font-semibold">Claims the judge checked</h2>
          <p className="mt-0.5 text-sm text-ink-muted">{deep.reason}</p>
          {/* A list, not a table: each claim and the judge's reason read as prose. */}
          <ul className="mt-3 divide-y divide-line border-y border-line">
            {deep.claims.map((claim, i) => (
              <li key={i} className="py-3">
                <div className="flex items-start justify-between gap-4">
                  <p className="max-w-[65ch] text-sm font-medium">{claim.claim}</p>
                  <span
                    className={`inline-flex shrink-0 items-center gap-1 text-sm font-semibold ${
                      claim.supported ? "text-pass" : blamed ? "text-cause" : "text-ink"
                    }`}
                  >
                    {claim.supported ? <CheckIcon size={14} /> : <CrossIcon size={14} />}
                    {claim.supported ? "Supported" : "Unsupported"}
                  </span>
                </div>
                {claim.reason && <p className="mt-1 max-w-[70ch] text-sm leading-6 text-ink-muted">{claim.reason}</p>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {params.length > 0 && (
        <section>
          <h2 className="font-semibold">Generation settings</h2>
          <dl className="mt-2 grid max-w-xl grid-cols-[auto_1fr] gap-x-6 gap-y-1 text-sm">
            {params.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-ink-muted">{k}</dt>
                <dd className="font-dash-mono text-[0.8125rem]">{v}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}
    </div>
  );
}

function PromptTab({ trace }: { trace: Trace }) {
  const p = trace.prompt;
  if (!p?.content) {
    return <p className="text-sm text-ink-muted">No prompt was captured for this trace. Pass it to the SDK to see it here.</p>;
  }
  return (
    <div>
      <div className="mb-3 flex items-center justify-between gap-4">
        <p className="text-sm text-ink-muted">
          {[p.templateName, p.version].filter(Boolean).join(", ") || "Prompt as sent to the model"}
        </p>
        <CopyButton text={p.content} label="Copy prompt" />
      </div>
      <pre className="max-h-[32rem] overflow-auto rounded border border-line bg-sunken p-4 font-dash-mono text-xs leading-6 whitespace-pre-wrap">
        {p.content}
      </pre>
    </div>
  );
}

const CHECKS = [
  { name: "Context relevance", stage: "Retrieval", quick: "contextRelevance", deep: "deepContextRelevance" },
  { name: "Groundedness", stage: "Grounding", quick: "groundedness", deep: "deepGroundedness" },
  { name: "Answer relevance", stage: "Answer", quick: "answerRelevance", deep: "deepAnswerRelevance" },
] as const;

function EvaluationTab({ trace }: { trace: Trace }) {
  const e = trace.evaluations;
  const sentence = provenanceSentence(trace.diagnosis.source, trace.deepStatus);
  return (
    <div>
      {sentence && <p className="mb-4 max-w-[70ch] text-sm text-ink-muted">{sentence}</p>}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[40rem] border-collapse text-sm">
          <thead>
            <tr className="border-b border-line-strong text-left text-xs text-ink-muted">
              <th scope="col" className="py-2 pr-4 font-medium">Check</th>
              <th scope="col" className="py-2 pr-4 font-medium">Estimate</th>
              <th scope="col" className="py-2 pr-4 font-medium">LLM judge</th>
              <th scope="col" className="py-2 font-medium">Reason given</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line align-top">
            {CHECKS.map((c) => {
              const quick = e[c.quick];
              const deep = e[c.deep];
              return (
                <tr key={c.name}>
                  <th scope="row" className="py-3 pr-4 text-left font-medium">
                    {c.name}
                    <span className="block text-xs font-normal text-ink-muted">{c.stage}</span>
                  </th>
                  <td className="py-3 pr-4 whitespace-nowrap">
                    {quick.label === "not_evaluated" ? (
                      <span className="text-ink-muted">Not run</span>
                    ) : (
                      <>
                        {quick.label.replaceAll("_", " ")}{" "}
                        <span className="font-dash-mono text-[0.8125rem] text-ink-muted">{quick.score.toFixed(2)}</span>
                      </>
                    )}
                  </td>
                  <td className="py-3 pr-4 whitespace-nowrap">
                    {deep ? deep.label.replaceAll("_", " ") : <span className="text-ink-muted">Not run</span>}
                  </td>
                  <td className="py-3 text-ink-muted">{deep?.reason || quick.reason}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FeedbackTab({ trace }: { trace: Trace }) {
  const items = trace.feedback ?? [];
  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,22rem)_1fr]">
      <section>
        <h2 className="font-semibold">Rate this answer</h2>
        <p className="mt-0.5 mb-3 text-sm text-ink-muted">Ratings are stored on the trace with an optional note.</p>
        <FeedbackWidget traceId={trace.traceId} />
      </section>
      <section>
        <h2 className="font-semibold">Feedback so far</h2>
        {items.length === 0 ? (
          <p className="mt-1 text-sm text-ink-muted">No feedback yet.</p>
        ) : (
          <ul className="mt-2 divide-y divide-line border-y border-line">
            {items.map((item, i) => {
              const up = item.rating === "thumbs_up";
              const Icon = up ? ThumbUpIcon : ThumbDownIcon;
              return (
                <li key={i} className="py-3">
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <span className="flex items-center gap-2 font-medium">
                      <Icon className={up ? "text-pass" : "text-ink-muted"} />
                      {up ? "Helpful" : "Not helpful"}
                    </span>
                    {item.createdAt && (
                      <time dateTime={item.createdAt} className="text-xs text-ink-muted">
                        {new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(item.createdAt))}
                      </time>
                    )}
                  </div>
                  {item.comment && <p className="mt-1 text-sm text-ink-muted">{item.comment}</p>}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}

function JsonTab({ trace }: { trace: Trace }) {
  const json = JSON.stringify(trace, null, 2);
  return (
    <div>
      <div className="mb-3 flex items-center justify-between gap-4">
        <p className="text-sm text-ink-muted">The trace as the dashboard reads it from the API.</p>
        <CopyButton text={json} label="Copy JSON" />
      </div>
      <pre className="max-h-[40rem] overflow-auto rounded border border-line bg-sunken p-4 font-dash-mono text-xs leading-5">
        {json}
      </pre>
    </div>
  );
}
