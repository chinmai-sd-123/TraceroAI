"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { usePrefersReducedMotion } from "./motion";

// The hero: one real run from the example app (trace 5f7bf901), shown as a
// case file built for a three-second read: the question, the answer with the
// bad claim marked, the three stage checks, and the verdict. It plays once on
// load (about four seconds) and holds; under reduced motion it starts finished.

const QUESTION = "is money within 10 days refunded?";
const CHUNKS = [
  "Refunds are processed within 5 to 7 business days after the request is approved. The approval review itself typically completes within 1 business day of submission.",
  "Refunds are always issued to the original payment method used for the purchase.",
  "Subscriptions can be refunded within 14 days of renewal.",
];
const ANSWER =
  "Yes, money is typically refunded within 10 days, as refunds are processed within 5 to 7 business days after approval, which usually occurs within 1 business day of submission.";
const MARK = "money is typically refunded within 10 days";
const STAGES = [
  { name: "Retrieval", word: "Passed" },
  { name: "Grounding", word: "Failed", cause: true },
  { name: "Answer", word: "Passed" },
];

// When each part arrives, in ms from the start.
const AT = { question: 150, questionFor: 450, context: 650, answer: 850, answerFor: 900, stage: 1900, stageGap: 260, ring: 2750, estimate: 2850, judge: 3250, verdict: 3550, end: 4100 };

const clamp = (v: number) => Math.min(1, Math.max(0, v));

export function CaseFile() {
  const reduced = usePrefersReducedMotion();
  const [t, setT] = useState(0);
  const [run, setRun] = useState(0);
  const frame = useRef(0);

  const play = useCallback(() => {
    cancelAnimationFrame(frame.current);
    const start = performance.now();
    const tick = (now: number) => {
      const elapsed = now - start;
      setT(elapsed);
      if (elapsed < AT.end) frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
  }, []);

  useEffect(() => {
    if (reduced) return;
    play();
    return () => cancelAnimationFrame(frame.current);
  }, [reduced, play, run]);

  const now = reduced ? Infinity : t;
  const after = (ms: number) => now >= ms;
  const question = QUESTION.slice(0, Math.round(QUESTION.length * clamp((now - AT.question) / AT.questionFor)));
  const answerLength = Math.round(ANSWER.length * clamp((now - AT.answer) / AT.answerFor));
  const typing = answerLength > 0 && answerLength < ANSWER.length;
  const done = (i: number) => after(AT.stage + i * AT.stageGap);
  const checking = STAGES.findIndex((_, i) => !done(i));

  return (
    <div data-thread="start" className="case-arrive relative">
      <div className="case-stack">
        <article aria-label="Case file for trace 5f7bf901" className="sheet glass-card overflow-hidden rounded-md border border-line-strong">
          <header className="flex items-center justify-between gap-3 border-b border-line bg-sunken/70 px-5 py-2.5 text-xs text-ink-muted">
            <span className="flex min-w-0 items-center gap-3">
              <span className="font-dash-mono text-ink">Case 5f7bf901</span>
              <span className="truncate max-sm:hidden">gpt-4o-mini · 1.68 s</span>
            </span>
            <button
              type="button"
              onClick={() => setRun((r) => r + 1)}
              disabled={reduced}
              className="rounded border border-line-strong bg-surface px-2 py-0.5 font-medium text-ink hover:bg-rail disabled:hidden"
            >
              Replay
            </button>
          </header>

          <div className="px-5 pt-4 pb-5">
            <p className="text-xs text-ink-muted">Question</p>
            <p className="mt-0.5 min-h-[1.6rem] text-[17px] font-semibold tracking-[-0.01em]">
              {question}
              {after(AT.question) && question.length < QUESTION.length && <span className="replay-caret" aria-hidden="true" />}
            </p>

            <details className={`group mt-2 text-xs text-ink-muted transition-opacity duration-300 ${after(AT.context) ? "opacity-100" : "opacity-0"}`}>
              <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 rounded hover:text-ink [&::-webkit-details-marker]:hidden">
                <span className="font-dash-mono text-[11px]">3 chunks · refund-policy · 223 ms</span>
                <span className="text-accent group-open:hidden">Show</span>
                <span className="hidden text-accent group-open:inline">Hide</span>
              </summary>
              <ol className="mt-2 space-y-1.5 border-l border-line pl-3">
                {CHUNKS.map((text, i) => (
                  <li key={i} className="leading-5">
                    <span className="mr-1.5 font-dash-mono text-ink-faint">[{i + 1}]</span>
                    {text}
                  </li>
                ))}
              </ol>
            </details>

            <p className="mt-4 text-xs text-ink-muted">Answer</p>
            <p className="mt-1 min-h-[4.6rem] text-[15px] leading-7">
              {after(AT.verdict) ? <Marked /> : ANSWER.slice(0, answerLength)}
              {typing && <span className="replay-caret" aria-hidden="true" />}
            </p>

            <ol className="mt-4 grid grid-cols-3 gap-2" aria-label="Stage checks">
              {STAGES.map((stage, i) => {
                const isDone = done(i);
                const isChecking = i === checking && after(AT.stage - 250);
                return (
                  <li
                    key={stage.name}
                    className={`relative rounded border px-3 pt-2.5 pb-2 text-sm ${isDone && stage.cause ? "border-cause/30 bg-cause-soft" : "border-line"}`}
                  >
                    <span className="absolute inset-0 overflow-hidden rounded" aria-hidden="true">
                      <span className={`absolute inset-x-0 top-0 h-[3px] transition-colors duration-300 ${!isDone ? "bg-line" : stage.cause ? "bg-cause" : "bg-pass"}`} />
                      {isChecking && <span className="replay-scan" />}
                    </span>
                    <p className="relative font-semibold">{stage.name}</p>
                    <p className={`relative text-xs ${isDone ? "replay-stamp text-ink" : "text-ink-faint"}`}>
                      {isDone ? stage.word : isChecking ? "Checking" : " "}
                    </p>
                    {stage.cause && after(AT.ring) && <Ring key={run} />}
                  </li>
                );
              })}
            </ol>

            <div className="mt-5 min-h-[7rem] border-t border-line pt-4" aria-live="polite">
              {after(AT.verdict) ? (
                <div className="replay-stamp">
                  <p className="text-xs text-ink-muted">Probable cause · Grounding</p>
                  <p className="mt-0.5 text-[26px] leading-tight font-bold tracking-[-0.02em] text-cause">Unsupported claim</p>
                  <p className="mt-1 text-[13px] leading-5 text-ink-muted">1 of 4 claims isn&apos;t in the retrieved context: it never says 10 days.</p>
                </div>
              ) : (
                <p className="text-xs text-ink-faint">{after(AT.stage - 250) ? "Checking each stage…" : " "}</p>
              )}
              <p className="mt-3 flex min-h-[1.375rem] flex-wrap items-center gap-2 text-xs text-ink-muted">
                {after(AT.estimate) && (
                  <span className="replay-in inline-flex flex-wrap items-center gap-2">
                    <span className={`block h-2 w-6 ${after(AT.judge) ? "bg-ink" : "hatch"}`} aria-hidden="true" />
                    {after(AT.judge) ? (
                      <>
                        <span className="rounded-[3px] border border-ink px-1.5 py-px font-semibold text-ink">Final · LLM judge</span>
                        <s className="text-ink-faint">Preliminary · term overlap: unclear</s>
                      </>
                    ) : (
                      <span className="rounded-[3px] border border-dashed border-ink-faint px-1.5 py-px">Preliminary · term overlap: unclear</span>
                    )}
                  </span>
                )}
              </p>
            </div>
          </div>
        </article>
      </div>
      <p className="mt-5 flex items-center gap-2 text-xs text-ink-muted">
        <span className="thread-pin" aria-hidden="true" />A real run from the example app, judged by an LLM.
      </p>
    </div>
  );
}

function Marked() {
  const at = ANSWER.indexOf(MARK);
  return (
    <>
      {ANSWER.slice(0, at)}
      <mark className="replay-mark rounded-[2px] px-0.5 text-ink">{MARK}</mark>
      {ANSWER.slice(at + MARK.length)}
    </>
  );
}

/** A reviewer's ring, drawn by hand around the failing stage. */
function Ring() {
  return (
    <svg
      className="case-ring pointer-events-none absolute -inset-x-2 -inset-y-2.5 h-[calc(100%+1.25rem)] w-[calc(100%+1rem)] overflow-visible"
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path
        d="M52 3 C 82 2, 99 14, 98 50 C 97 86, 80 98, 48 97 C 16 96, 2 84, 3 50 C 4 18, 20 5, 58 6"
        pathLength={1}
        fill="none"
        stroke="var(--color-cause)"
        strokeWidth="2"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
