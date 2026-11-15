"use client";

import { useEffect, useRef, useState } from "react";

import { CheckIcon, CrossIcon } from "@/components/icons";

import { usePrefersReducedMotion } from "./motion";

// "Anatomy of a diagnosis": one real trace from the example app, played
// through the pipeline as the reader scrolls. The chunks, the claims and the
// judge's verdicts are the trace's own (trace 5f7bf901 and its recovery run).

const QUESTION = "is money within 10 days refunded?";
const CHUNKS = [
  { title: "refund-policy", text: "Refunds are processed within 5 to 7 business days after the request is approved. The approval review itself typically completes within 1 business day of submission…" },
  { title: "refund-policy", text: "Refunds are always issued to the original payment method used for the purchase…" },
  { title: "refund-policy", text: "Subscriptions can be refunded within 14 days of renewal…" },
];
const ANSWER =
  "Yes, money is typically refunded within 10 days, as refunds are processed within 5 to 7 business days after approval, which usually occurs within 1 business day of submission.";
const CLAIMS = [
  { text: "Money is typically refunded within 10 days.", supported: false },
  { text: "Refunds are processed within 5 to 7 business days after the request is approved.", supported: true },
  { text: "Approval review typically completes within 1 business day of submission.", supported: true },
  { text: "Most customers receive their full refund within a week and a half at most.", supported: true },
];

const STEPS = [
  { at: 0.0, title: "A question comes in", body: "Your app calls the SDK with the user's question." },
  { at: 0.12, title: "Retrieval", body: "Your retriever returns three chunks of the refund policy. TraceroAI records each one." },
  { at: 0.3, title: "Prompt and generation", body: "The chunks go into the prompt and the model answers. Every step is timed." },
  { at: 0.52, title: "The judge reads the answer", body: "It splits the answer into claims and checks each against the chunks." },
  { at: 0.74, title: "Probable cause", body: "One claim isn't in the context, so grounding failed: an unsupported claim." },
  { at: 0.86, title: "Recovery", body: "The agent regenerated with a stricter prompt. On attempt 3 the judge found every claim supported." },
];

const clamp = (v: number) => Math.min(1, Math.max(0, v));
const seg = (p: number, a: number, b: number) => clamp((p - a) / (b - a));
const ease = (t: number) => 1 - Math.pow(1 - t, 3);

export function Anatomy() {
  const reduced = usePrefersReducedMotion();
  const section = useRef<HTMLElement | null>(null);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (reduced) return;
    let frame = 0;
    const update = () => {
      frame = 0;
      const el = section.current;
      if (!el) return;
      // Below the desktop layout nothing is pinned: show the finished trace.
      if (window.innerWidth < 1024) {
        setProgress(1);
        return;
      }
      const box = el.getBoundingClientRect();
      const travel = box.height - window.innerHeight;
      setProgress(travel > 0 ? clamp(-box.top / travel) : 1);
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [reduced]);

  const p = reduced ? 1 : progress;
  const step = STEPS.reduce((current, s, i) => (p >= s.at ? i : current), 0);

  const qIn = ease(seg(p, 0, 0.06));
  const chunkIn = (i: number) => ease(seg(p, 0.12 + i * 0.04, 0.2 + i * 0.04));
  const folded = ease(seg(p, 0.3, 0.38)); // chunks fold into the prompt
  const typed = Math.round(ANSWER.length * seg(p, 0.38, 0.5));
  const judging = seg(p, 0.52, 0.72);
  const lensAt = Math.min(CLAIMS.length - 1, Math.floor(judging * CLAIMS.length));
  const claimDone = (i: number) => judging * CLAIMS.length > i + 0.6;
  const stamp = seg(p, 0.74, 0.79);
  const healed = seg(p, 0.86, 0.92);

  return (
    <section ref={section} aria-labelledby="anatomy-title" className={`relative ${reduced ? "" : "lg:h-[480vh]"}`}>
      {/* Pinned while the reader scrolls through it; under reduced motion it's
          an ordinary section showing the finished trace. */}
      <div className={reduced ? "" : "lg:sticky lg:top-14 lg:flex lg:h-[calc(100vh-3.5rem)] lg:items-center"}>
        <div className="mx-auto grid w-full max-w-[84rem] gap-10 px-4 py-14 sm:px-8 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)] lg:gap-16 lg:py-0">
          {/* The narrative, one step lit at a time. */}
          <div>
            <h2 id="anatomy-title" className="text-[2rem] leading-tight font-bold tracking-[-0.025em]">
              Anatomy of a diagnosis
            </h2>
            <p className="mt-2 text-sm text-ink-muted">One real trace from the example app, start to finish.</p>
            <ol className="relative mt-8 space-y-5 border-l border-line pl-5">
              <span
                className="absolute top-0 -left-px w-px bg-accent transition-[height] duration-150"
                style={{ height: `${p * 100}%` }}
                aria-hidden="true"
              />
              {STEPS.map((s, i) => (
                <li key={s.title} className={`transition-opacity duration-300 ${i === step || reduced ? "opacity-100" : i < step ? "opacity-55" : "opacity-30"}`}>
                  <p className={`font-semibold ${i === step && !reduced ? "text-ink" : ""}`}>{s.title}</p>
                  <p className="mt-0.5 text-sm leading-6 text-ink-muted">{s.body}</p>
                </li>
              ))}
            </ol>
          </div>

          {/* The stage. */}
          <div className="relative overflow-hidden rounded-md border border-line-strong bg-surface lg:min-h-[34rem]" aria-hidden="true">
            <div className="relative grid grid-cols-[minmax(0,1fr)] gap-4 p-5 sm:p-7 lg:h-full">
              {/* Question */}
              <div style={{ opacity: qIn, transform: `translateY(${(1 - qIn) * 16}px)` }}>
                <p className="text-xs text-ink-muted">Question</p>
                <p className="mt-0.5 text-lg font-semibold">{QUESTION}</p>
              </div>

              {/* Retrieved chunks, folding into the prompt */}
              <div className="relative">
                <p className="text-xs text-ink-muted" style={{ opacity: chunkIn(0) }}>
                  {folded > 0.5 ? "Prompt: question + 3 chunks" : "Retrieved"}
                </p>
                <div
                  className="mt-1.5 grid gap-2 transition-[gap] sm:grid-cols-3"
                  style={{ gap: `${8 - folded * 8}px` }}
                >
                  {CHUNKS.map((c, i) => (
                    <div
                      key={i}
                      className="rounded border border-line-strong bg-surface px-3 py-2 text-xs leading-5"
                      style={{
                        opacity: chunkIn(i),
                        transform: `translateX(${(1 - chunkIn(i)) * 80}px) scale(${1 - folded * 0.06})`,
                        borderColor: folded > 0.5 ? "var(--color-accent)" : undefined,
                      }}
                    >
                      <p className="font-dash-mono text-[11px] text-ink-muted">
                        [{i + 1}] {c.title}
                      </p>
                      <p className="mt-1 line-clamp-3 text-ink-muted">{c.text}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Answer, typed */}
              <div style={{ opacity: typed > 0 ? 1 : 0.25 }}>
                <p className="text-xs text-ink-muted">Answer · gpt-4o-mini</p>
                <p className="mt-1 min-h-[3.5rem] rounded border border-line bg-sunken/70 px-3 py-2 text-sm leading-6">
                  {ANSWER.slice(0, typed)}
                  {typed > 0 && typed < ANSWER.length && <span className="replay-caret" />}
                </p>
              </div>

              {/* The judge's claims, with a lens moving down them */}
              <div className="relative" style={{ opacity: judging > 0 ? 1 : 0.2 }}>
                <p className="text-xs text-ink-muted">Claims the judge checked</p>
                <ul className="relative mt-1.5 space-y-1.5">
                  {judging > 0 && judging < 1 && (
                    <span
                      className="pointer-events-none absolute -inset-x-2 h-8 rounded border-2 border-accent bg-accent/5 transition-[top] duration-200"
                      style={{ top: `${lensAt * 2.125}rem` }}
                    />
                  )}
                  {CLAIMS.map((claim, i) => {
                    const done = claimDone(i);
                    return (
                      <li key={i} className="flex items-start gap-2 text-sm lg:h-[1.75rem] lg:items-center">
                        <span
                          className={`flex size-5 shrink-0 items-center justify-center rounded-full transition-all duration-300 ${
                            !done ? "border border-line-strong" : claim.supported ? "bg-pass text-white" : "bg-cause text-white"
                          }`}
                        >
                          {done && (claim.supported ? <CheckIcon size={12} /> : <CrossIcon size={12} />)}
                        </span>
                        <span className={`lg:truncate ${done && !claim.supported ? "font-semibold text-cause" : ""}`}>{claim.text}</span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            </div>

            {/* The stamps: overlaid on desktop, in their own row on small screens. */}
            <div className="relative flex flex-wrap gap-3 px-5 pb-5 lg:static lg:p-0">
            {stamp > 0 && (
              <div
                className="rounded border-[3px] border-cause bg-surface/90 px-4 py-2 text-cause lg:absolute lg:right-6 lg:bottom-8"
                style={{
                  opacity: stamp * (1 - healed * 0.3),
                  transform: `rotate(-8deg) scale(${1.6 - ease(stamp) * 0.6})`,
                }}
              >
                <p className="text-xs font-semibold">Probable cause · grounding</p>
                <p className="text-xl font-bold tracking-[-0.01em]">Unsupported claim</p>
              </div>
            )}
            {healed > 0 && (
              <div
                className="rounded border-[3px] border-pass bg-surface/95 px-4 py-2 text-pass lg:absolute lg:right-10 lg:bottom-24"
                style={{ opacity: healed, transform: `rotate(4deg) scale(${1.5 - ease(healed) * 0.5})` }}
              >
                <p className="text-xs font-semibold">Recovery run · attempt 3</p>
                <p className="text-xl font-bold tracking-[-0.01em]">Healthy</p>
              </div>
            )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
