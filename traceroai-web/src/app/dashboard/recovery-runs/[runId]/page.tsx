import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { getTraces } from "@/lib/api";
import type { Trace } from "@/lib/trace-types";

import { CopyButton } from "@/components/copy-button";
import { ArrowRightIcon } from "@/components/icons";
import {
  DiagnosisBadge,
  PageFrame,
  PageHeader,
  ProvenanceMark,
  StageSequence,
  diagnosisName,
  formatMs,
  formatWhen,
  isHealthy,
} from "../../ui";
import { actionWords } from "../recovery";

// One RecoveryAgent run, read left to right: the first attempt and how it
// failed, each decision the agent took, each retry, and the final outcome.

export default async function RecoveryRunPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  const { traces } = await getTraces({ recoveryRunId: runId, sort: "oldest", limit: 20 });
  const attempts = traces
    .filter((t) => t.recovery)
    .sort((a, b) => a.recovery!.attempt - b.recovery!.attempt);
  if (attempts.length === 0) notFound();

  const first = attempts[0];
  const last = attempts[attempts.length - 1];
  const healthy = isHealthy(last.diagnosis.label);

  return (
    <PageFrame>
      <PageHeader
        crumbs={[{ label: "Recovery runs", href: "/dashboard/recovery-runs" }, { label: runId.slice(0, 8) }]}
        title={first.query.original}
        description={`${attempts.length} attempt${attempts.length === 1 ? "" : "s"}, ${formatWhen(first.timestamp)} to ${formatWhen(last.timestamp)}`}
        actions={<CopyButton text={runId} label="Copy run id" />}
      />

      <section aria-labelledby="sequence" className="mt-6">
        <h2 id="sequence" className="sr-only">
          What happened
        </h2>
        <ol className="flex flex-col gap-3 lg:flex-row lg:items-stretch">
          {attempts.map((attempt, i) => (
            <AttemptStep key={attempt.traceId} attempt={attempt} previous={attempts[i - 1]} />
          ))}
          <li className="flex lg:w-56 lg:shrink-0">
            <div
              className={`flex w-full flex-col justify-center rounded border-2 px-4 py-4 ${
                healthy ? "border-pass bg-pass-soft" : "border-ink-muted bg-sunken"
              }`}
            >
              <p className="text-xs font-semibold text-ink-muted">Final outcome</p>
              <p className={`mt-1 text-lg font-semibold ${healthy ? "text-pass" : ""}`}>
                {healthy ? "Healthy answer" : diagnosisName(last.diagnosis.label)}
              </p>
              <p className="mt-1 text-sm text-ink-muted">
                {healthy
                  ? attempts.length === 1
                    ? "No retry was needed."
                    : `Fixed on attempt ${last.recovery!.attempt}.`
                  : `Still failing after ${attempts.length} attempt${attempts.length === 1 ? "" : "s"}. The documents may not cover this question.`}
              </p>
            </div>
          </li>
        </ol>
      </section>

      {attempts.length > 1 && <WhatChanged first={first} last={last} />}
    </PageFrame>
  );
}

function AttemptStep({ attempt, previous }: { attempt: Trace; previous?: Trace }) {
  const topK = topKOf(attempt);
  const previousTopK = previous ? topKOf(previous) : null;
  return (
    <>
      {previous && (
        <li className="flex items-center lg:w-44 lg:shrink-0" aria-label="Agent decision">
          <div className="w-full rounded border border-dashed border-accent px-3 py-3 text-sm">
            <p className="flex items-center gap-1.5 text-xs font-semibold text-accent">
              Agent decision <ArrowRightIcon size={12} className="max-lg:rotate-90" />
            </p>
            <p className="mt-1 font-medium">{capitalise(actionWords(attempt.recovery!.action))}</p>
            <p className="mt-0.5 text-xs text-ink-muted">
              because attempt {previous.recovery!.attempt} was {diagnosisName(previous.diagnosis.label).toLowerCase()}
            </p>
            {topK !== previousTopK && topK != null && previousTopK != null && (
              <p className="mt-1 font-dash-mono text-xs">
                top_k {previousTopK} → {topK}
              </p>
            )}
          </div>
        </li>
      )}
      <li className="flex min-w-0 flex-1">
        <Link
          href={`/dashboard/traces/${attempt.traceId}`}
          className="flex w-full flex-col rounded border border-line-strong px-4 py-4 hover:bg-sunken"
        >
          <p className="flex items-center justify-between gap-2 text-xs text-ink-muted">
            <span className="font-semibold">
              {previous ? `Retry, attempt ${attempt.recovery!.attempt}` : "Original attempt"}
            </span>
            <span className="font-dash-mono">{attempt.traceId.slice(0, 8)}</span>
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <DiagnosisBadge label={attempt.diagnosis.label} size="sm" />
            <ProvenanceMark source={attempt.diagnosis.source} status={attempt.deepStatus} size="sm" />
          </div>
          <p className="mt-2 line-clamp-3 text-sm text-ink-muted">{attempt.diagnosis.reason}</p>
          <div className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-1 pt-3 text-xs text-ink-muted">
            <StageSequence trace={attempt} />
          <dl className="flex flex-wrap items-center gap-x-4 gap-y-1">
            {topKOf(attempt) != null && (
              <div className="flex gap-1">
                <dt>top_k</dt>
                <dd className="font-dash-mono text-ink">{topKOf(attempt)}</dd>
              </div>
            )}
            <div className="flex gap-1">
              <dt>chunks</dt>
              <dd className="text-ink">{attempt.retrieval.chunks.length}</dd>
            </div>
            <div className="flex gap-1">
              <dt>took</dt>
              <dd className="text-ink">{formatMs(attempt.latency.totalMs)}</dd>
            </div>
          </dl>
          </div>
        </Link>
      </li>
    </>
  );
}

/** The difference between the first and the last attempt. */
function WhatChanged({ first, last }: { first: Trace; last: Trace }) {
  const key = (c: Trace["retrieval"]["chunks"][number]) => c.chunkId || c.textPreview.slice(0, 80);
  const before = new Map(first.retrieval.chunks.map((c) => [key(c), c]));
  const after = new Map(last.retrieval.chunks.map((c) => [key(c), c]));
  const added = [...after.entries()].filter(([k]) => !before.has(k)).map(([, c]) => c);
  const removed = [...before.entries()].filter(([k]) => !after.has(k)).map(([, c]) => c);
  const promptChanged = (first.prompt?.content ?? "") !== (last.prompt?.content ?? "");

  return (
    <section aria-labelledby="changed" className="mt-10">
      <h2 id="changed" className="font-semibold">
        What changed from the first attempt to the last
      </h2>
      <dl className="mt-3 grid grid-cols-[8rem_minmax(0,1fr)] gap-y-2 border-y border-line py-3 text-sm">
        <Row label="top_k">
          {topKOf(first) === topKOf(last) ? (
            <>
              {topKOf(last) ?? "not recorded"} <span className="text-ink-muted">(unchanged)</span>
            </>
          ) : (
            <>
              {topKOf(first) ?? "not recorded"}{" "}
              <ArrowRightIcon size={12} className="inline align-middle text-ink-muted" /> {topKOf(last) ?? "not recorded"}
            </>
          )}
        </Row>
        <Row label="Chunks added">
          {added.length === 0 ? (
            <span className="text-ink-muted">None</span>
          ) : (
            <ul className="space-y-0.5">
              {added.map((c) => (
                <li key={key(c)}>
                  {c.documentTitle}
                  {c.source && c.source !== c.documentTitle && (
                    <span className="ml-2 font-dash-mono text-xs text-ink-muted">{c.source}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Row>
        <Row label="Chunks dropped">
          {removed.length === 0 ? <span className="text-ink-muted">None</span> : removed.map((c) => c.documentTitle).join(", ")}
        </Row>
        <Row label="Prompt">{promptChanged ? "Changed" : "Unchanged"}</Row>
      </dl>
      <div className="mt-5 grid gap-5 md:grid-cols-2">
        <Answer label={`Answer, attempt ${first.recovery!.attempt}`} trace={first} />
        <Answer label={`Answer, attempt ${last.recovery!.attempt}`} trace={last} />
      </div>
    </section>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-ink-muted">{label}</dt>
      <dd>{children}</dd>
    </>
  );
}

function Answer({ label, trace }: { label: string; trace: Trace }) {
  return (
    <figure className="rounded border border-line">
      <figcaption className="flex items-center justify-between gap-2 border-b border-line bg-sunken px-4 py-2 text-xs">
        <span className="font-semibold">{label}</span>
        <DiagnosisBadge label={trace.diagnosis.label} size="sm" />
      </figcaption>
      <blockquote className="px-4 py-3 text-sm leading-6 whitespace-pre-line">
        {trace.generation?.answer || <span className="text-ink-muted">No answer recorded.</span>}
      </blockquote>
    </figure>
  );
}

function topKOf(trace: Trace): number | null {
  return trace.recovery?.topK ?? trace.retrieval.config?.finalTopK ?? null;
}

function capitalise(text: string) {
  return text.charAt(0).toUpperCase() + text.slice(1);
}
