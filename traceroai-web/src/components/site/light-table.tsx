"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { CheckIcon, CrossIcon } from "@/components/icons";

import { usePrefersReducedMotion } from "./motion";

// The light table: one real run (trace 5f7bf901 from the example app) laid on
// a backlit table and lifted apart into its layers as the reader scrolls. The
// layer that went wrong is the red one. Click a layer to lay it flat and read
// it; it's the same content, not a picture of it.

const QUESTION = "is money within 10 days refunded?";
const CHUNKS = [
  "Refunds are processed within 5 to 7 business days after the request is approved. The approval review itself typically completes within 1 business day of submission.",
  "Refunds are always issued to the original payment method used for the purchase.",
  "Subscriptions can be refunded within 14 days of renewal.",
];
const ANSWER_BEFORE = "Yes, ";
const ANSWER_MARK = "money is typically refunded within 10 days";
const ANSWER_AFTER =
  ", as refunds are processed within 5 to 7 business days after approval, which usually occurs within 1 business day of submission.";
const CLAIMS = [
  { text: "Money is typically refunded within 10 days.", supported: false },
  { text: "Refunds are processed within 5 to 7 business days after the request is approved.", supported: true },
  { text: "Approval review typically completes within 1 business day of submission.", supported: true },
  { text: "Most customers receive their full refund within a week and a half at most.", supported: true },
];

type Layer = { name: string; note: string; fault?: boolean; body: ReactNode };

const LAYERS: Layer[] = [
  {
    name: "Question",
    note: "What the user asked, as your app sent it.",
    body: (
      <>
        <p className="text-[19px] leading-snug font-semibold tracking-[-0.01em]">{QUESTION}</p>
        <p className="mt-3 font-dash-mono text-[11px] text-ink-muted">trace 5f7bf901 · project recovery-agent · dev</p>
      </>
    ),
  },
  {
    name: "Retrieved context",
    note: "Three chunks of the refund policy, in rank order.",
    body: (
      <ol className="space-y-1.5">
        {CHUNKS.map((text, i) => (
          <li key={i} className="flex gap-2 text-[12.5px] leading-5">
            <span className="font-dash-mono text-[11px] text-ink-faint">[{i + 1}]</span>
            <span className="line-clamp-2 text-ink-muted">{text}</span>
          </li>
        ))}
        <li className="pt-1 font-dash-mono text-[11px] text-ink-faint">vector · top_k 3 · 223 ms</li>
      </ol>
    ),
  },
  {
    name: "Answer",
    note: "What the model said. One claim isn't in the context.",
    fault: true,
    body: (
      <>
        <p className="text-[13.5px] leading-6">
          {ANSWER_BEFORE}
          <mark className="bg-transparent text-cause underline decoration-cause decoration-2 underline-offset-4">{ANSWER_MARK}</mark>
          {ANSWER_AFTER}
        </p>
        <p className="mt-2 font-dash-mono text-[11px] text-ink-muted">gpt-4o-mini · 410 tokens · 1,451 ms</p>
      </>
    ),
  },
  {
    name: "The judge's checks",
    note: "The answer split into claims, each checked against the chunks.",
    body: (
      <ul className="space-y-1.5">
        {CLAIMS.map((claim) => (
          <li key={claim.text} className="flex items-start gap-2 text-[12.5px] leading-5">
            <span
              className={`mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full text-white ${claim.supported ? "bg-pass" : "bg-cause"}`}
            >
              {claim.supported ? <CheckIcon size={10} /> : <CrossIcon size={10} />}
            </span>
            <span className={claim.supported ? "text-ink-muted" : "font-semibold text-cause"}>{claim.text}</span>
          </li>
        ))}
      </ul>
    ),
  },
  {
    name: "Verdict",
    note: "One probable cause, and who decided it.",
    body: (
      <>
        <p className="text-xs text-ink-muted">Probable cause · Grounding</p>
        <p className="mt-0.5 text-[22px] leading-tight font-bold tracking-[-0.015em] text-cause">Unsupported claim</p>
        <p className="mt-1.5 text-[13px] text-ink-muted">1 of 4 claims are not supported by the context.</p>
        <p className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-[3px] border border-ink px-1.5 py-px font-semibold">Final · LLM judge</span>
          <s className="text-ink-faint">Preliminary · term overlap: unclear</s>
        </p>
      </>
    ),
  },
];

const clamp = (v: number) => Math.min(1, Math.max(0, v));
const ease = (t: number) => 1 - Math.pow(1 - t, 3);

export function LightTable() {
  const reduced = usePrefersReducedMotion();
  const section = useRef<HTMLElement | null>(null);
  const [progress, setProgress] = useState(0);
  const [wide, setWide] = useState(false);
  const [open, setOpen] = useState<number | null>(null);

  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const el = section.current;
      const isWide = window.innerWidth >= 1024;
      setWide(isWide);
      if (!el || !isWide) return;
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
  }, []);

  useEffect(() => {
    if (open === null) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(null);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  // Narrow screens and reduced motion get the layers as a plain stack.
  if (!wide || reduced) {
    return (
      <section id="taken-apart" aria-labelledby="table-title" data-thread="pin" className="light-table-room scroll-mt-14 border-y border-line">
        <div className="mx-auto max-w-[84rem] px-4 py-16 sm:px-8">
          <Intro />
          <ol className="mt-10 grid gap-4 md:grid-cols-2">
            {LAYERS.map((layer, i) => (
              <li key={layer.name} className={`sheet rounded-[5px] border p-5 ${layer.fault ? "border-cause/50 bg-cause-soft" : "border-line-strong bg-surface"}`}>
                <SheetHead layer={layer} n={i + 1} />
                <div className="mt-3">{layer.body}</div>
              </li>
            ))}
          </ol>
        </div>
      </section>
    );
  }

  // 0 to 0.28: the stack tilts and lifts apart. 0.28 to 0.92: each layer in
  // turn slides out to be read. After that the stack holds, open.
  const p = progress;
  const lift = ease(clamp(p / 0.28));
  const walk = clamp((p - 0.28) / 0.64);
  const current = p < 0.28 ? -1 : Math.min(LAYERS.length - 1, Math.floor(walk * LAYERS.length));
  const flat = open !== null;

  return (
    <section ref={section} id="taken-apart" aria-labelledby="table-title" data-thread="pin" className="light-table-room relative h-[340vh] scroll-mt-14 border-y border-line">
      <div className="sticky top-14 flex h-[calc(100vh-3.5rem)] items-center overflow-hidden">
        <div className="mx-auto grid w-full max-w-[84rem] grid-cols-[minmax(0,21rem)_minmax(0,1fr)] items-center gap-12 px-8">
          <div>
            <Intro />
            <ol className="mt-8 space-y-1" aria-label="Layers of the run">
              {LAYERS.map((layer, i) => {
                const lit = flat ? open === i : current === i;
                return (
                  <li key={layer.name}>
                    <button
                      type="button"
                      onClick={() => setOpen(open === i ? null : i)}
                      aria-pressed={open === i}
                      className={`group flex w-full items-baseline gap-3 rounded px-2 py-1.5 text-left transition-colors ${lit ? "bg-surface" : "hover:bg-surface/70"}`}
                    >
                      <span className={`font-dash-mono text-xs ${layer.fault ? "text-cause" : "text-ink-faint"}`}>{i + 1}</span>
                      <span>
                        <span className={`block text-sm font-semibold ${layer.fault ? "text-cause" : lit ? "text-ink" : "text-ink-muted"}`}>
                          {layer.name}
                        </span>
                        <span className={`block text-xs leading-5 text-ink-muted transition-opacity ${lit ? "opacity-100" : "opacity-0"}`}>
                          {layer.note}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
            <p className="mt-4 pl-2 text-xs text-ink-muted">
              {flat ? (
                <button type="button" onClick={() => setOpen(null)} className="font-medium text-accent hover:underline">
                  Back to the stack (Esc)
                </button>
              ) : (
                "Click a layer to lay it flat and read it."
              )}
            </p>
          </div>

          {/* The table and the stack on it. Decorative for assistive tech: the
              list on the left names every layer, and opening one shows it flat. */}
          <div className="light-table relative flex h-[min(38rem,calc(100vh-9rem))] items-center justify-center rounded-md">
            <div className="lt-stage" style={{ perspective: "2200px" }}>
              <div
                className="lt-stack"
                style={{
                  transform: flat ? "none" : `translateX(${lift * -40}px) rotateX(${lift * 57}deg) rotateZ(${lift * -28}deg)`,
                }}
              >
                {LAYERS.map((layer, i) => {
                  const z = flat ? 0 : (i - (LAYERS.length - 1) / 2) * 112 * lift;
                  const out = !flat && current === i ? 1 : 0;
                  const hidden = flat && open !== i;
                  return (
                    <div
                      key={layer.name}
                      aria-hidden={hidden || undefined}
                      onClick={() => setOpen(open === i ? null : i)}
                      className={`lt-sheet sheet acetate cursor-pointer rounded-[5px] border p-5 ${
                        layer.fault ? "acetate-fault border-cause/50" : "border-line-strong"
                      }`}
                      style={{
                        transform: `translate3d(${out * 170}px, 0, ${z}px)`,
                        opacity: hidden ? 0 : 1,
                        pointerEvents: hidden ? "none" : undefined,
                        zIndex: flat && open === i ? 10 : i,
                      }}
                    >
                      <SheetHead layer={layer} n={i + 1} />
                      <div className="mt-3">{layer.body}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Intro() {
  return (
    <>
      <h2 id="table-title" className="focus-in text-[2.5rem] leading-[1.05] font-bold tracking-[-0.03em] text-balance">
        The run, taken apart
      </h2>
      <p className="mt-4 max-w-[40ch] text-[17px] leading-8 text-ink-muted">
        One real run from the example app, separated into what went in, what came out, and what the judge found. The red
        layer is where it went wrong.
      </p>
    </>
  );
}

function SheetHead({ layer, n }: { layer: Layer; n: number }) {
  return (
    <p className="flex items-baseline justify-between gap-3 border-b border-line pb-2 text-xs">
      <span className={`font-semibold ${layer.fault ? "text-cause" : "text-ink"}`}>{layer.name}</span>
      <span className="font-dash-mono text-ink-faint">{n} / 5</span>
    </p>
  );
}
