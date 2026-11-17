import Link from "next/link";
import type { ReactNode } from "react";

import type { StepKind, TraceStep } from "@/lib/trace-types";

import { formatCost, formatMs } from "../../ui";

// The run's steps as a tree laid on a time axis: which step called which, in
// order, and how long each took. Selecting a step (a link, so each has a URL)
// shows what went in and what came out. Errors are amber, as everywhere in the
// dashboard; red stays for a diagnosis's probable cause.

export const KIND_NAMES: Record<StepKind, string> = {
  agent: "Agent",
  chain: "Chain",
  llm: "Model call",
  tool: "Tool",
  retriever: "Retrieval",
  embedding: "Embedding",
  reranker: "Rerank",
  guardrail: "Guardrail",
};

const MAX_INDENT = 8;

/** A measured duration. formatMs treats 0 as "not measured"; here a step that
 * took under a millisecond really did. */
function took(ms: number): string {
  return ms < 1 ? "<1 ms" : formatMs(ms);
}

type Row = { step: TraceStep; depth: number };

/** Steps in tree order: each step followed by its children, in the order sent. */
export function treeOrder(steps: TraceStep[]): Row[] {
  const ids = new Set(steps.map((s) => s.stepId));
  const children = new Map<string | null, TraceStep[]>();
  for (const step of steps) {
    const parent = step.parentId && ids.has(step.parentId) ? step.parentId : null;
    children.set(parent, [...(children.get(parent) ?? []), step]);
  }
  const rows: Row[] = [];
  const seen = new Set<string>();
  const visit = (parent: string | null, depth: number) => {
    for (const step of children.get(parent) ?? []) {
      if (seen.has(step.stepId)) continue; // a malformed loop can't hang the page
      seen.add(step.stepId);
      rows.push({ step, depth });
      visit(step.stepId, depth + 1);
    }
  };
  visit(null, 0);
  return rows;
}

/** The step to open first: the first that errored, else the first. */
export function defaultStepId(steps: TraceStep[]): string | undefined {
  return (steps.find((s) => s.status === "error") ?? steps[0])?.stepId;
}

export function StepsView({
  steps,
  selected,
  hrefFor,
}: {
  steps: TraceStep[];
  selected: string | undefined;
  hrefFor: (stepId: string) => string;
}) {
  const rows = treeOrder(steps);
  const start = Math.min(...steps.map((s) => Date.parse(s.startedAt)));
  const end = Math.max(...steps.map((s) => Date.parse(s.endedAt ?? s.startedAt)));
  const longest = Math.max(0, ...steps.filter((s) => !s.parentId).map((s) => s.durationMs ?? 0));
  const span = Math.max(1, end - start, longest);
  const active = steps.find((s) => s.stepId === selected) ?? steps[0];
  const errors = steps.filter((s) => s.status === "error").length;

  return (
    <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <nav aria-label="Steps" className="@container overflow-hidden rounded border border-line">
        <div className="flex items-baseline justify-between border-b border-line bg-sunken px-4 py-2 text-xs text-ink-muted">
          <span>
            {steps.length} step{steps.length === 1 ? "" : "s"}
            {errors > 0 && <span className="text-warn"> · {errors} with an error</span>}
          </span>
          <span className="max-sm:hidden">{took(span)}</span>
        </div>
        <ol className="divide-y divide-line">
          {rows.map(({ step, depth }) => {
            const left = ((Date.parse(step.startedAt) - start) / span) * 100;
            const width = step.durationMs != null ? Math.max(0.6, (step.durationMs / span) * 100) : 0;
            const isActive = step.stepId === active?.stepId;
            const failed = step.status === "error";
            return (
              <li key={step.stepId}>
                <Link
                  href={hrefFor(step.stepId)}
                  aria-current={isActive ? "true" : undefined}
                  scroll={false}
                  className={`grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 px-4 py-2 text-sm @[34rem]:grid-cols-[minmax(0,1fr)_7rem_4rem] ${
                    isActive ? "bg-accent-soft" : "hover:bg-sunken"
                  }`}
                >
                  <span
                    className="flex min-w-0 items-baseline gap-2"
                    style={{ paddingLeft: `${Math.min(depth, MAX_INDENT) * 12}px` }}
                  >
                    {depth > 0 && <span className="text-line-strong" aria-hidden="true">└</span>}
                    <span className={`w-[4.25rem] shrink-0 text-xs ${failed ? "text-warn" : "text-ink-muted"}`}>
                      {KIND_NAMES[step.kind]}
                    </span>
                    <span className={`truncate ${failed ? "font-medium text-warn" : isActive ? "font-medium text-ink" : ""}`}>
                      {step.name}
                    </span>
                  </span>
                  {/* Where the step sits in the run's time; decorative, the duration is the number. */}
                  <span className="relative hidden h-2 bg-sunken @[34rem]:block" aria-hidden="true">
                    {width > 0 && (
                      <span
                        className={`absolute top-0 h-2 ${failed ? "bg-warn" : step.kind === "llm" ? "bg-accent" : "bg-ink-muted/55"}`}
                        style={{ left: `${Math.min(left, 99.4)}%`, width: `${Math.min(width, 100 - left)}%` }}
                      />
                    )}
                  </span>
                  <span className="text-right font-dash-mono text-xs text-ink-muted tabular-nums">
                    {step.durationMs != null ? took(step.durationMs) : "—"}
                  </span>
                </Link>
              </li>
            );
          })}
        </ol>
      </nav>

      {active && <StepDetail step={active} offsetMs={Date.parse(active.startedAt) - start} />}
    </div>
  );
}

const SUMMARY_LABELS: Array<[string, string]> = [
  ["model", "Model"],
  ["provider", "Provider"],
  ["prompt_tokens", "Input tokens"],
  ["completion_tokens", "Output tokens"],
  ["total_tokens", "Total tokens"],
  ["cost_usd", "Cost (USD)"],
  ["temperature", "Temperature"],
  ["tool", "Tool"],
  ["agent", "Agent"],
  ["prompt_version", "Prompt version"],
  ["session_id", "Session"],
  ["user_id", "User"],
];

function StepDetail({ step, offsetMs }: { step: TraceStep; offsetMs: number }) {
  const cost = typeof step.attributes.cost_usd === "number" ? formatCost(step.attributes.cost_usd) : null;
  // Cost is shown with the timing above, so it isn't repeated in the details.
  const summary = SUMMARY_LABELS.filter(([key]) => step.attributes[key] != null && !(key === "cost_usd" && cost));
  const known = new Set(SUMMARY_LABELS.map(([key]) => key));
  const otel = step.attributes.otel;
  const rest = Object.entries(step.attributes).filter(([key]) => !known.has(key) && key !== "otel");
  return (
    <section aria-label={`Step: ${step.name}`} className="min-w-0 rounded border border-line">
      <div className="border-b border-line bg-sunken px-5 py-3">
        <p className="text-xs text-ink-muted">{KIND_NAMES[step.kind]}</p>
        <h3 className="mt-0.5 font-semibold break-words">{step.name}</h3>
      </div>
      <div className="space-y-6 px-5 py-5">
        <dl className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
          <Fact label="Started">{offsetMs < 1 ? "+0 ms" : `+${formatMs(offsetMs)}`}</Fact>
          <Fact label="Took">{step.durationMs != null ? took(step.durationMs) : "not recorded"}</Fact>
          {cost && <Fact label="Cost">{cost}</Fact>}
          <Fact label="Status">
            <span className={step.status === "error" ? "font-medium text-warn" : ""}>
              {step.status === "error" ? "Error" : step.status === "ok" ? "OK" : "Not set"}
            </span>
          </Fact>
        </dl>
        {step.statusMessage && (
          <p className="rounded border border-warn/30 bg-warn-soft px-3 py-2 text-sm text-warn">{step.statusMessage}</p>
        )}

        <Block title="Input">
          <Content value={step.input} />
        </Block>
        <Block title="Output">
          <Content value={step.output} />
        </Block>

        {(summary.length > 0 || rest.length > 0) && (
          <Block title="Details">
            <dl className="grid grid-cols-[minmax(0,8rem)_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-sm">
              {summary.map(([key, label]) => (
                <Row key={key} label={label} value={step.attributes[key]} />
              ))}
              {rest.map(([key, value]) => (
                <Row key={key} label={key} value={value} />
              ))}
            </dl>
          </Block>
        )}
        {otel != null && typeof otel === "object" && Object.keys(otel).length > 0 && (
          <details className="text-sm">
            <summary className="cursor-pointer font-medium text-accent">OpenTelemetry attributes</summary>
            <Json value={otel} />
          </details>
        )}
      </div>
    </section>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <dt className="text-ink-muted">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function Row({ label, value }: { label: string; value: unknown }) {
  return (
    <>
      <dt className="text-ink-muted break-words">{label}</dt>
      <dd className="font-dash-mono text-[13px] break-words">{typeof value === "object" ? JSON.stringify(value) : String(value)}</dd>
    </>
  );
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h4 className="text-xs font-medium text-ink-muted">{title}</h4>
      <div className="mt-1.5">{children}</div>
    </section>
  );
}

/** A step's input or output, shown as what it is: messages, documents, text or JSON. */
function Content({ value }: { value: unknown }) {
  if (value == null || value === "") return <p className="text-sm text-ink-muted">Not recorded.</p>;
  if (typeof value === "string") {
    return <p className="max-h-80 overflow-y-auto text-[15px] leading-7 whitespace-pre-line">{value}</p>;
  }
  if (isRecord(value) && Array.isArray(value.messages)) {
    return (
      <ol className="space-y-2">
        {value.messages.map((message, i) => {
          const m = isRecord(message) ? message : {};
          const calls = Array.isArray(m.tool_calls) ? m.tool_calls.filter(isRecord) : [];
          return (
            <li key={i} className="rounded border border-line px-3 py-2">
              <p className="text-xs font-medium text-ink-muted">{typeof m.role === "string" ? m.role : "message"}</p>
              {(typeof m.content === "string" || calls.length === 0) && (
                <p className="mt-0.5 text-sm leading-6 whitespace-pre-line">
                  {typeof m.content === "string" ? m.content : <span className="text-ink-muted">No text.</span>}
                </p>
              )}
              {calls.map((call, j) => (
                <div key={j} className="mt-1 text-sm">
                  <p>
                    Calls <span className="font-dash-mono font-medium">{String(call.name)}</span>
                  </p>
                  {call.arguments != null && (
                    <pre className="mt-1 overflow-x-auto rounded bg-sunken px-2 py-1 font-dash-mono text-xs leading-5">
                      {typeof call.arguments === "string" ? call.arguments : JSON.stringify(call.arguments, null, 2)}
                    </pre>
                  )}
                </div>
              ))}
            </li>
          );
        })}
      </ol>
    );
  }
  if (isRecord(value) && Array.isArray(value.documents)) {
    return (
      <ol className="space-y-2">
        {value.documents.map((document, i) => {
          const d = isRecord(document) ? document : {};
          return (
            <li key={i} className="rounded border border-line px-3 py-2 text-sm">
              <p className="flex justify-between gap-3 font-dash-mono text-xs text-ink-muted">
                <span className="truncate">[{i + 1}] {d.id != null ? String(d.id) : "document"}</span>
                {typeof d.score === "number" && <span>{d.score.toFixed(3)}</span>}
              </p>
              <p className="mt-1 leading-6 whitespace-pre-line">
                {typeof d.content === "string" ? d.content : <span className="text-ink-muted">Text not recorded.</span>}
              </p>
            </li>
          );
        })}
      </ol>
    );
  }
  return <Json value={value} />;
}

function Json({ value }: { value: unknown }) {
  return (
    <pre className="mt-1.5 max-h-80 overflow-auto rounded bg-sunken px-3 py-2 font-dash-mono text-[12.5px] leading-5 whitespace-pre-wrap break-words">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
