import Link from "next/link";
import type { ReactNode } from "react";

import type { DeepStatus, DiagnosisSource, Trace, TraceDiagnosis } from "@/lib/trace-types";

// Shared building blocks for the dashboard. Server components only (no hooks),
// so any page can use them.
//
// Two rules run through all of them:
// - Red marks the probable cause and nothing else. A failed stage that isn't
//   the cause is drawn in ink; errors elsewhere in the UI use amber.
// - A verdict the LLM judge made is drawn solid. One an estimate made (term
//   overlap, embedding similarity) is drawn hatched, and called "Preliminary".

// --- diagnosis -------------------------------------------------------------

export const DIAGNOSIS_NAMES: Record<TraceDiagnosis, string> = {
  healthy_answer: "Healthy",
  correct_refusal: "Correct refusal",
  retrieval_miss: "Retrieval miss",
  low_context_relevance: "Weak retrieval",
  unsupported_claim: "Unsupported claim",
  wrong_answer: "Wrong answer",
  needs_review: "Needs review",
  not_diagnosed: "Not diagnosed",
};

export function diagnosisName(label: string): string {
  return DIAGNOSIS_NAMES[label as TraceDiagnosis] ?? label.replaceAll("_", " ");
}

export type Tone = "pass" | "cause" | "warn" | "none";

export function diagnosisTone(label: string): Tone {
  if (label === "healthy_answer" || label === "correct_refusal") return "pass";
  if (causeStage(label)) return "cause";
  if (label === "needs_review") return "warn";
  return "none";
}

export function isHealthy(label: string): boolean {
  return diagnosisTone(label) === "pass";
}

/** The pipeline stage a failing diagnosis blames, if any. */
export function causeStage(label: string): StageKey | null {
  if (label === "retrieval_miss" || label === "low_context_relevance") return "retrieval";
  if (label === "unsupported_claim") return "grounding";
  if (label === "wrong_answer") return "answer";
  return null;
}

const TONE_TEXT: Record<Tone, string> = {
  pass: "text-pass",
  cause: "text-cause",
  warn: "text-warn",
  none: "text-ink-muted",
};

const TONE_BADGE: Record<Tone, string> = {
  pass: "bg-pass-soft text-pass",
  cause: "bg-cause-soft text-cause",
  warn: "bg-warn-soft text-warn",
  none: "bg-sunken text-ink-muted",
};

export function DiagnosisBadge({ label, size = "md" }: { label: string; size?: "sm" | "md" }) {
  return (
    <span
      className={`inline-flex items-center rounded font-semibold whitespace-nowrap ${
        size === "sm" ? "px-1.5 py-px text-xs" : "px-2 py-0.5 text-sm"
      } ${TONE_BADGE[diagnosisTone(label)]}`}
    >
      {diagnosisName(label)}
    </span>
  );
}

// --- provenance ------------------------------------------------------------

const ESTIMATE_NAMES: Record<Exclude<DiagnosisSource, "judge">, string> = {
  embedding: "embedding estimate",
  lexical: "term-overlap estimate",
};

/** Final (the LLM judge decided) or Preliminary (an estimate did), with what
 * is still to come. */
export function ProvenanceMark({
  source,
  status,
  size = "md",
}: {
  source: DiagnosisSource | undefined;
  status: DeepStatus | undefined;
  size?: "sm" | "md";
}) {
  if (!source) return null;
  const final = source === "judge";
  const detail = final
    ? status === "partial"
      ? "LLM judge, some checks failed"
      : "LLM judge"
    : `${ESTIMATE_NAMES[source]}${
        status === "pending"
          ? ", judge pending"
          : status === "failed"
            ? ", judge failed"
            : ""
      }`;
  // In lists the word alone; the method is in the tooltip and for screen readers.
  const compact = size === "sm";
  return (
    <span
      title={compact ? detail : undefined}
      className={`inline-flex items-center gap-1 rounded-[3px] border whitespace-nowrap ${
        final ? "border-ink text-ink" : "border-dashed border-ink-faint text-ink-muted"
      } ${compact ? "px-1 text-[11px] leading-4" : "px-1.5 py-px text-xs"}`}
    >
      <span className="font-semibold">{final ? "Final" : "Preliminary"}</span>
      {compact ? (
        <span className="sr-only">, {detail}</span>
      ) : (
        <>
          <span aria-hidden="true">·</span>
          {detail}
        </>
      )}
    </span>
  );
}

// --- pipeline stages ---------------------------------------------------------

export type StageKey = "retrieval" | "grounding" | "answer";
export type StageState = "pass" | "fail" | "review" | "unknown";
export type Stage = {
  key: StageKey;
  name: string;
  question: string; // what this stage's check asks
  state: StageState;
  judged: boolean; // the LLM judge decided it (otherwise an estimate)
  method: string; // what decided it, in words
  reason?: string;
  cause: boolean; // the diagnosis blames this stage
  overruled?: { method: string; state: StageState }; // the estimate the judge replaced
};

function quickState(label: string): StageState {
  if (label === "pass") return "pass";
  if (label === "fail") return "fail";
  if (label === "needs_review") return "review";
  return "unknown";
}

function judgeState(label: string | undefined): StageState | null {
  if (label === "relevant" || label === "grounded") return "pass";
  if (label === "irrelevant" || label === "not_grounded") return "fail";
  if (label === "needs_review") return "review";
  return null; // missing or errored: fall back to the estimate
}

/** The three stages a RAG answer passes through, each with the verdict of the
 * best evaluation available: the LLM judge's when it ran, the estimate's
 * otherwise. */
export function stagesOf(trace: Trace): Stage[] {
  const e = trace.evaluations;
  const blamed = causeStage(trace.diagnosis.label);
  // Relevance estimates use embeddings when the server had them; groundedness
  // is always term overlap.
  const relevanceMethod = trace.evalMethods?.embedding ? "embedding similarity" : "term overlap";
  const stage = (
    key: StageKey,
    name: string,
    question: string,
    deep: { label: string; reason: string } | undefined,
    quick: { label: string; reason: string },
    method: string,
  ): Stage => {
    const judged = judgeState(deep?.label);
    const estimate = quickState(quick.label);
    if (judged) {
      return {
        key, name, question, state: judged, judged: true, method: "LLM judge",
        reason: deep?.reason, cause: blamed === key,
        overruled:
          estimate !== "unknown" && estimate !== judged ? { method, state: estimate } : undefined,
      };
    }
    return {
      key, name, question, state: estimate, judged: false, method,
      reason: quick.reason, cause: blamed === key,
    };
  };
  const stages = [
    stage("retrieval", "Retrieval", "Did the retrieved context match the question?",
      e.deepContextRelevance, e.contextRelevance, relevanceMethod),
    stage("grounding", "Grounding", "Is every claim supported by that context?",
      e.deepGroundedness, e.groundedness, "term overlap"),
    stage("answer", "Answer", "Does the answer address the question?",
      e.deepAnswerRelevance, e.answerRelevance, relevanceMethod),
  ];
  // The diagnosis can blame a stage whose own check passed: a refusal of an
  // answerable question is a wrong answer even though the refusal is "on
  // topic". The diagnosis wins, with its reason.
  return stages.map((s) =>
    s.cause && s.state !== "fail" ? { ...s, state: "fail", reason: trace.diagnosis.reason } : s,
  );
}

export const STATE_WORDS: Record<StageState, string> = {
  pass: "Passed",
  fail: "Failed",
  review: "Unclear",
  unknown: "Not checked",
};

// Text colour of each segment; the fill is the current colour, solid or hatched.
function segmentColor(s: Stage): string {
  if (s.cause) return "text-cause";
  if (s.state === "fail") return "text-ink-muted";
  if (s.state === "pass") return "text-pass";
  if (s.state === "review") return "text-warn";
  return "text-line-strong";
}

function Segment({ stage, className }: { stage: Stage; className: string }) {
  return (
    <span
      className={`block ${segmentColor(stage)} ${
        stage.judged || stage.state === "unknown" ? "bg-current" : "hatch"
      } ${className}`}
    />
  );
}

/** One stage's verdict as a small square: colour by state, solid when judged,
 * hatched when estimated. */
export function StageMark({ stage }: { stage: Stage }) {
  return (
    <span title={`${stage.name}: ${STATE_WORDS[stage.state].toLowerCase()}${stage.cause ? " (probable cause)" : ""}`}>
      <Segment stage={stage} className="size-2.5 rounded-[1px]" />
    </span>
  );
}

/** Compact sequence for lists: Retrieval > Grounding > Answer, the probable
 * cause in red, estimates hatched. */
export function StageSequence({ trace }: { trace: Trace }) {
  const stages = stagesOf(trace);
  const summary = stages
    .map(
      (s) =>
        `${s.name}: ${STATE_WORDS[s.state].toLowerCase()}${s.cause ? " (probable cause)" : ""}${
          s.judged || s.state === "unknown" ? "" : ", estimated"
        }`,
    )
    .join("; ");
  return (
    <span className="inline-flex shrink-0 items-center gap-[3px]" role="img" aria-label={summary} title={summary}>
      {stages.map((s) => (
        <Segment key={s.key} stage={s} className="h-2 w-5 rounded-[1px]" />
      ))}
    </span>
  );
}

/** The trace page's ruled sequence: one column per stage with its verdict,
 * who reached it, and the reason. */
export function StageDocket({
  trace,
  inspectHref,
}: {
  trace: Trace;
  inspectHref?: (stage: StageKey) => string; // link each stage to its step in the timeline
}) {
  const stages = stagesOf(trace);
  return (
    <ol className="grid border border-line-strong md:grid-cols-3">
      {stages.map((s, i) => (
        <li
          key={s.key}
          className={`group relative flex flex-col border-line px-5 pt-5 pb-4 max-md:[&:not(:first-child)]:border-t md:[&:not(:first-child)]:border-l ${
            s.cause ? "bg-cause-soft" : "bg-surface"
          } ${inspectHref ? "has-[a:focus-visible]:outline-2 has-[a:focus-visible]:-outline-offset-2 has-[a:focus-visible]:outline-accent" : ""}`}
        >
          <Segment stage={s} className="absolute inset-x-0 top-0 h-[3px]" />
          <div className="flex items-baseline justify-between gap-3">
            <h3 className="font-semibold">
              <span className="mr-1.5 font-medium text-ink-faint">{i + 1}</span>
              {inspectHref ? (
                // The whole card is the link (the ::after covers it); it opens the
                // stage's step in the execution timeline and scrolls there.
                <Link
                  href={inspectHref(s.key)}
                  title={`Inspect ${s.name.toLowerCase()} in the execution timeline`}
                  className="underline-offset-2 group-hover:underline after:absolute after:inset-0 focus-visible:outline-none"
                >
                  {s.name}
                </Link>
              ) : (
                s.name
              )}
            </h3>
            <p
              className={`text-sm font-semibold ${
                s.cause
                  ? "text-cause"
                  : s.state === "pass"
                    ? "text-pass"
                    : s.state === "review"
                      ? "text-warn"
                      : s.state === "fail"
                        ? "text-ink"
                        : "text-ink-faint"
              }`}
            >
              {STATE_WORDS[s.state]}
            </p>
          </div>
          <p className="mt-1 text-sm text-ink-muted">{s.question}</p>
          {s.reason && <p className="mt-3 text-sm leading-6 text-pretty">{s.reason}</p>}
          <div className="mt-auto pt-4">
            {s.cause && (
              <p className="mb-2">
                <span className="rounded-[3px] border border-cause px-1.5 py-px text-xs font-semibold text-cause">
                  Probable cause
                </span>
              </p>
            )}
            <p className="text-xs text-ink-muted">
              {s.state === "unknown"
                ? "No check ran on this stage."
                : s.judged
                  ? "Final: decided by the LLM judge."
                  : `Preliminary: estimated from ${s.method}.`}
            </p>
            {s.overruled && (
              <p className="mt-1 text-xs text-ink-muted">
                <s>
                  Preliminary ({s.overruled.method}): {STATE_WORDS[s.overruled.state].toLowerCase()}
                </s>{" "}
                <span className="sr-only">(overruled by the judge)</span>
              </p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}

// --- page structure ----------------------------------------------------------

/** Padding and width for ordinary pages (the trace page runs full bleed). */
export function PageFrame({ children }: { children: ReactNode }) {
  return <div className="mx-auto w-full max-w-[76rem] px-4 py-6 sm:px-8 lg:py-8">{children}</div>;
}

export function PageHeader({
  title,
  description,
  actions,
  crumbs,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  crumbs?: Array<{ label: ReactNode; href?: string }>;
}) {
  return (
    <header className="border-b border-line pb-5">
      {crumbs && crumbs.length > 0 && (
        <nav aria-label="Breadcrumb" className="mb-2 text-sm text-ink-muted">
          <ol className="flex flex-wrap items-center gap-1.5">
            {crumbs.map((c, i) => (
              <li key={i} className="flex items-center gap-1.5">
                {i > 0 && <span aria-hidden="true" className="text-line-strong">/</span>}
                {c.href ? (
                  <Link href={c.href} className="hover:text-ink hover:underline">
                    {c.label}
                  </Link>
                ) : (
                  <span aria-current="page">{c.label}</span>
                )}
              </li>
            ))}
          </ol>
        </nav>
      )}
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-[-0.015em] text-balance">{title}</h1>
          {description && <p className="mt-1.5 max-w-2xl text-sm text-ink-muted">{description}</p>}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </header>
  );
}

/** A flat, ruled panel: a heading row over its content. */
export function Panel({
  title,
  description,
  actions,
  children,
  className = "",
  flush = false,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  flush?: boolean; // content runs to the edges (tables, lists)
}) {
  return (
    <section className={`rounded border border-line bg-surface ${className}`}>
      <div className="flex items-start justify-between gap-4 px-5 pt-4">
        <div className="min-w-0">
          <h2 className="font-semibold">{title}</h2>
          {description && <p className="mt-0.5 text-sm text-ink-muted">{description}</p>}
        </div>
        {actions && <div className="shrink-0">{actions}</div>}
      </div>
      <div className={flush ? "mt-3" : "px-5 pt-3 pb-5"}>{children}</div>
    </section>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded border border-dashed border-line-strong px-6 py-10 text-center">
      <p className="font-semibold">{title}</p>
      {children && <div className="mx-auto mt-1.5 max-w-md text-sm text-ink-muted">{children}</div>}
    </div>
  );
}

/** Underline tabs as links, so each tab has a URL and works without JS. */
export function LinkTabs({
  tabs,
  active,
  label,
}: {
  tabs: Array<{ key: string; label: ReactNode; href: string }>;
  active: string;
  label: string;
}) {
  return (
    // On narrow screens the tabs scroll sideways; the fade at the right edge
    // shows there are more, and the end padding lets the last one clear it.
    <nav
      aria-label={label}
      className="overflow-x-auto border-b border-line max-sm:[mask-image:linear-gradient(to_right,black_80%,transparent)]"
    >
      <ul className="flex min-w-max gap-6 max-sm:pr-10">
        {tabs.map((t) => {
          const on = t.key === active;
          return (
            <li key={t.key}>
              <Link
                href={t.href}
                scroll={false}
                aria-current={on ? "page" : undefined}
                className={`-mb-px block border-b-2 py-2.5 text-sm transition-colors ${
                  on
                    ? "border-accent font-semibold text-ink"
                    : "border-transparent text-ink-muted hover:border-line-strong hover:text-ink"
                }`}
              >
                {t.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** Segmented links for a small set of options (time range, filters). */
export function Segmented({
  options,
  active,
  label,
}: {
  options: Array<{ key: string; label: ReactNode; href: string }>;
  active: string;
  label: string;
}) {
  return (
    <nav aria-label={label}>
      <ul className="flex rounded border border-line-strong bg-surface p-0.5 text-sm">
        {options.map((o) => {
          const on = o.key === active;
          return (
            <li key={o.key}>
              <Link
                href={o.href}
                aria-current={on ? "true" : undefined}
                className={`block rounded-[3px] px-2.5 py-1 whitespace-nowrap ${
                  on ? "bg-accent font-medium text-white" : "text-ink-muted hover:bg-sunken hover:text-ink"
                }`}
              >
                {o.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export { TONE_TEXT };

// --- formatting ----------------------------------------------------------------

export function formatMs(ms: number | null | undefined): string {
  if (ms == null || ms <= 0) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(ms >= 10000 ? 0 : 2)} s` : `${Math.round(ms)} ms`;
}

export function formatWhen(timestamp: string): string {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(timestamp));
}

export function formatCost(usd: number | null | undefined): string | null {
  if (usd == null || usd <= 0) return null;
  return usd < 0.01 ? `$${usd.toFixed(5)}` : `$${usd.toFixed(3)}`;
}

/** Build a dashboard URL, dropping empty parameters. */
export function hrefWith(path: string, params: Record<string, string | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) search.set(key, value);
  }
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}
