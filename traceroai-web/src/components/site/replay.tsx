"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ArrowRightIcon } from "@/components/icons";

import { usePrefersReducedMotion } from "./motion";

export type ReplayStage = {
  name: string;
  state: "pass" | "fail" | "review";
  note: string;
  cause?: boolean;
};

export type ReplayCase = {
  tab: string;
  traceId: string;
  model: string;
  latency: string;
  question: string;
  answer: string;
  unsupported?: string; // the part of the answer the judge found unsupported
  stages: ReplayStage[];
  estimate: string; // what the quick estimate said before the judge ran
  verdict: { label: string; tone: "cause" | "pass"; reason: string };
  recovery?: Array<{ label: string; healthy: boolean; action?: string }>;
};

// Phases of one replay. Durations are how long each phase holds, in ms.
const PHASES = ["question", "typing", "retrieval", "grounding", "answer", "estimate", "judge", "verdict", "hold"] as const;
type Phase = (typeof PHASES)[number];
const HOLD: Record<Phase, number> = {
  question: 500,
  typing: 0, // ends when the answer is typed
  retrieval: 750,
  grounding: 750,
  answer: 750,
  estimate: 900,
  judge: 900,
  verdict: 2400,
  hold: 2200,
};
const STATE_WORD = { pass: "Passed", fail: "Failed", review: "Unclear" };

/** Replays real traces from the example app the way TraceroAI investigates
 * them, one stage at a time, and moves on to the next case. */
export function InvestigationReplay({ cases }: { cases: ReplayCase[] }) {
  const reduced = usePrefersReducedMotion();
  const [index, setIndex] = useState(0);
  const [step, setPhase] = useState<number>(0);
  const [typedCount, setTyped] = useState(0);
  const [playing, setPlaying] = useState(true);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const item = cases[index];
  // Under reduced motion every case shows its finished state.
  const phase = reduced ? PHASES.indexOf("hold") : step;
  const typed = reduced ? item.answer.length : typedCount;
  const at = (p: Phase) => phase >= PHASES.indexOf(p);

  const start = useCallback((i: number) => {
    setIndex(i);
    setPhase(0);
    setTyped(0);
  }, []);

  // Advance through the phases; typing runs character by character.
  useEffect(() => {
    if (!playing || reduced) return;
    const name = PHASES[phase];
    if (name === "typing") {
      if (typed < item.answer.length) {
        timer.current = setTimeout(() => setTyped((n) => Math.min(item.answer.length, n + 3)), 16);
      } else {
        timer.current = setTimeout(() => setPhase((p) => p + 1), 250);
      }
    } else if (name === "hold") {
      timer.current = setTimeout(() => start((index + 1) % cases.length), HOLD.hold);
    } else {
      timer.current = setTimeout(() => setPhase((p) => p + 1), HOLD[name]);
    }
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [phase, typed, playing, reduced, item, index, cases.length, start]);

  const stagePhase = (i: number) => PHASES.indexOf(["retrieval", "grounding", "answer"][i] as Phase);
  const answerText = item.answer.slice(0, typed);
  const showUnsupported = item.unsupported && at("grounding") && phase > stagePhase(1);

  return (
    <div className="relative">
      <div className="overflow-hidden rounded-md border border-line-strong bg-surface">
        <div className="flex items-center justify-between gap-3 border-b border-line bg-sunken px-4 py-2.5 text-xs text-ink-muted">
          <span className="flex min-w-0 items-center gap-3">
            <span className="font-dash-mono">trace {item.traceId}</span>
            <span className="truncate max-sm:hidden">
              {item.model} · {item.latency}
            </span>
          </span>
          <button
            type="button"
            onClick={() => (playing ? setPlaying(false) : (setPlaying(true), phase >= PHASES.length - 1 && start(index)))}
            className="rounded border border-line-strong bg-surface px-2 py-0.5 font-medium text-ink hover:bg-rail"
            aria-label={playing ? "Pause the replay" : "Play the replay"}
          >
            {playing && !reduced ? "Pause" : "Play"}
          </button>
        </div>

        <div className="px-5 pt-4 pb-5">
          <p className="text-xs text-ink-muted">Question</p>
          <p key={`q-${index}`} className="replay-in mt-0.5 text-[17px] font-semibold tracking-[-0.01em]">
            {item.question}
          </p>

          <p className="mt-4 text-xs text-ink-muted">Answer</p>
          <p className="mt-1 min-h-[4.5rem] rounded border border-line bg-sunken/60 px-3 py-2 text-sm leading-6">
            {showUnsupported ? (
              <AnswerWithMark text={item.answer} mark={item.unsupported!} />
            ) : (
              <>
                {answerText}
                {PHASES[phase] === "typing" && <span className="replay-caret" aria-hidden="true" />}
              </>
            )}
          </p>

          <ol className="mt-4 grid grid-cols-3 border border-line-strong text-sm" aria-label="Stage checks">
            {item.stages.map((stage, i) => {
              const checking = phase === stagePhase(i);
              const done = phase > stagePhase(i);
              const color = !done
                ? "bg-line-strong"
                : stage.cause
                  ? "bg-cause"
                  : stage.state === "pass"
                    ? "bg-pass"
                    : stage.state === "review"
                      ? "bg-warn"
                      : "bg-ink-muted";
              return (
                <li
                  key={stage.name}
                  className={`relative overflow-hidden px-3 pt-3 pb-2.5 sm:min-h-[7.5rem] [&:not(:first-child)]:border-l [&:not(:first-child)]:border-line ${
                    done && stage.cause ? "bg-cause-soft" : ""
                  }`}
                >
                  <span className={`absolute inset-x-0 top-0 h-[3px] transition-colors duration-300 ${color}`} aria-hidden="true" />
                  {checking && <span className="replay-scan" aria-hidden="true" />}
                  <p className="flex items-baseline justify-between gap-2 font-semibold">
                    {stage.name}
                    <span
                      className={`text-xs ${done ? "replay-stamp" : ""} ${
                        !done ? "text-ink-faint" : stage.cause ? "text-cause" : stage.state === "pass" ? "text-pass" : stage.state === "review" ? "text-warn" : "text-ink"
                      }`}
                    >
                      {done ? STATE_WORD[stage.state] : checking ? "Checking" : ""}
                    </span>
                  </p>
                  <p className={`mt-1.5 text-xs leading-5 text-ink-muted transition-opacity duration-300 max-sm:hidden ${done ? "opacity-100" : "opacity-0"}`}>
                    {stage.note}
                  </p>
                </li>
              );
            })}
          </ol>

          <div className="mt-4 flex min-h-[2.25rem] flex-wrap items-center gap-x-3 gap-y-2 text-sm">
            {at("estimate") && (
              <span className="replay-in inline-flex items-center gap-2 text-xs text-ink-muted">
                <span className={`block h-2.5 w-7 text-ink-muted ${at("judge") ? "bg-ink" : "hatch"} transition-colors duration-300`} aria-hidden="true" />
                {at("judge") ? (
                  <>
                    <span className="rounded-[3px] border border-ink px-1.5 py-px font-semibold text-ink">Final · LLM judge</span>
                    <s className="text-ink-faint">{item.estimate}</s>
                  </>
                ) : (
                  <span className="rounded-[3px] border border-dashed border-ink-faint px-1.5 py-px">{item.estimate}</span>
                )}
              </span>
            )}
          </div>

          <div className="mt-3 min-h-[3.25rem] border-t border-line pt-3">
            {at("verdict") && (
              <div className="replay-stamp">
                <p className="flex flex-wrap items-baseline gap-x-2.5">
                  <span className="text-xs text-ink-muted">{item.verdict.tone === "cause" ? "Probable cause" : "Diagnosis"}</span>
                  <strong className={`text-lg ${item.verdict.tone === "cause" ? "text-cause" : "text-pass"}`}>{item.verdict.label}</strong>
                </p>
                <p className="mt-0.5 text-xs text-ink-muted">{item.verdict.reason}</p>
              </div>
            )}
          </div>

          {item.recovery && at("verdict") && (
            <ol className="mt-3 flex flex-wrap items-center gap-1.5 text-xs" aria-label="Recovery run">
              {item.recovery.map((step, i) => (
                <li key={i} className="replay-in flex items-center gap-1.5" style={{ animationDelay: `${300 + i * 350}ms` }}>
                  {step.action && (
                    <span className="flex items-center gap-1 text-ink-muted">
                      <ArrowRightIcon size={12} />
                      {step.action}
                      <ArrowRightIcon size={12} />
                    </span>
                  )}
                  <span className={`rounded border px-1.5 py-0.5 ${step.healthy ? "border-pass font-semibold text-pass" : "border-line-strong"}`}>
                    {i + 1}. {step.label}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>

      <div role="tablist" aria-label="Replayed traces" className="mt-3 grid grid-cols-3 gap-2">
        {cases.map((c, i) => {
          const on = i === index;
          return (
            <button
              key={c.tab}
              type="button"
              role="tab"
              aria-selected={on}
              onClick={() => {
                setPlaying(true);
                start(i);
              }}
              className={`relative overflow-hidden rounded border px-2.5 pt-2 pb-2.5 text-left text-xs ${
                on ? "border-accent bg-surface font-semibold text-ink" : "border-line bg-surface/70 text-ink-muted hover:text-ink"
              }`}
            >
              {c.tab}
              {on && !reduced && (
                <span
                  className="absolute bottom-0 left-0 h-0.5 bg-accent transition-[width] duration-700 ease-linear"
                  style={{ width: `${(phase / (PHASES.length - 1)) * 100}%` }}
                  aria-hidden="true"
                />
              )}
            </button>
          );
        })}
      </div>
      <p className="mt-2 text-xs text-ink-muted">Replayed from real traces in the example app, judged by an LLM.</p>
    </div>
  );
}

function AnswerWithMark({ text, mark }: { text: string; mark: string }) {
  const at = text.toLowerCase().indexOf(mark.toLowerCase());
  if (at === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, at)}
      <mark className="replay-mark bg-cause-soft text-ink decoration-cause decoration-2 underline-offset-4">{text.slice(at, at + mark.length)}</mark>
      {text.slice(at + mark.length)}
    </>
  );
}
