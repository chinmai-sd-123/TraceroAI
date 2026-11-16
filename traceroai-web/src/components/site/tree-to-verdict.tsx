"use client";

import { useEffect, useRef, useState } from "react";

import { usePrefersReducedMotion } from "./motion";

// "A trace isn't an answer": the stored record of the hero's run (trace
// 5f7bf901) as a step tree. As the reader scrolls, every line that isn't the
// answer folds away; three remain, and become the diagnosis.

type Row = { depth: number; last?: boolean; name: string; value: string; keep?: "step" | "cause" | "decided" };

const ROWS: Row[] = [
  { depth: 0, name: "trace", value: "5f7bf901 · recovery-agent · dev · 1,680 ms" },
  { depth: 1, name: "query", value: '"is money within 10 days refunded?"' },
  { depth: 1, name: "retrieval", value: "vector · top_k 3 · 223 ms" },
  { depth: 2, name: "[1] refund-policy", value: '"Refunds are processed within 5 to 7 business days…"' },
  { depth: 2, name: "[2] refund-policy", value: '"Refunds are always issued to the original payment…"' },
  { depth: 2, last: true, name: "[3] refund-policy", value: '"Subscriptions can be refunded within 14 days…"' },
  { depth: 1, name: "generation", value: "gpt-4o-mini · 410 tokens · 1,451 ms" },
  { depth: 2, last: true, name: "answer", value: '"Yes, money is typically refunded within 10 days, as…"' },
  { depth: 1, name: "quick checks", value: "term overlap" },
  { depth: 2, name: "context_relevance", value: "pass" },
  { depth: 2, name: "groundedness", value: "needs_review" },
  { depth: 2, last: true, name: "answer_relevance", value: "pass" },
  { depth: 1, name: "judge checks", value: "LLM judge" },
  { depth: 2, name: "context_relevance", value: "relevant" },
  { depth: 2, name: "claim_groundedness", value: "not_grounded · 1 of 4 claims", keep: "step" },
  { depth: 3, last: true, name: "claim", value: '"Money is typically refunded within 10 days." unsupported', keep: "cause" },
  { depth: 2, last: true, name: "answer_relevance", value: "relevant" },
  { depth: 1, last: true, name: "diagnosis", value: "unsupported_claim · source judge", keep: "decided" },
];

const VERDICT = [
  { key: "step", label: "Step", value: <span className="font-semibold text-cause">Grounding</span> },
  {
    key: "cause",
    label: "Cause",
    value: (
      <>
        <span className="font-semibold text-cause">Unsupported claim.</span> &ldquo;Money is typically refunded within 10
        days&rdquo; isn&apos;t in the retrieved context.
      </>
    ),
  },
  {
    key: "decided",
    label: "Decided by",
    value: (
      <>
        The LLM judge, so it&apos;s final. The quick estimate had said <span className="whitespace-nowrap">&ldquo;unclear&rdquo;.</span>
      </>
    ),
  },
];

const clamp = (v: number) => Math.min(1, Math.max(0, v));

export function TreeToVerdict() {
  const reduced = usePrefersReducedMotion();
  const section = useRef<HTMLElement | null>(null);
  const [progress, setProgress] = useState(0);
  const [wide, setWide] = useState(false);

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

  const pinned = wide && !reduced;
  const p = pinned ? progress : 1;
  // Rows fold one after another between 0.08 and 0.62 of the scroll.
  const others = ROWS.filter((r) => !r.keep);
  const fold = (row: Row) => {
    if (row.keep) return 0;
    const i = others.indexOf(row);
    return clamp((p - 0.08 - i * 0.024) / 0.14);
  };
  const remaining = ROWS.filter((r) => fold(r) < 0.5).length;
  const settled = p > 0.62;
  const lineIn = (i: number) => clamp((p - 0.6 - i * 0.07) / 0.1);

  const tree = (
    <div className="overflow-hidden rounded-md border border-line-strong bg-surface">
      <p className="flex items-baseline justify-between border-b border-line bg-sunken px-4 py-2.5 text-xs text-ink-muted">
        <span>What the trace shows you</span>
        <span className="font-dash-mono tabular-nums">{pinned ? remaining : ROWS.length} lines</span>
      </p>
      <ol className="px-4 py-3 font-dash-mono text-[12px]" aria-label="The run's step tree">
        {ROWS.map((row, i) => {
          const f = fold(row);
          const lit = row.keep && settled;
          return (
            <li
              key={i}
              className={`tree-row flex overflow-hidden whitespace-nowrap ${lit ? "text-cause" : row.keep && pinned ? "text-ink" : "text-ink-muted"}`}
              style={{ height: `${(1 - f) * 1.45}rem`, opacity: 1 - f, alignItems: "center" }}
              aria-hidden={f > 0.5 || undefined}
            >
              <span className="whitespace-pre text-ink-faint/60 select-none" aria-hidden="true">
                {row.depth === 0 ? "" : `${"│ ".repeat(row.depth - 1)}${row.last ? "└ " : "├ "}`}
              </span>
              <span className={`${row.depth === 0 || row.keep ? "font-medium" : ""} ${lit ? "" : row.depth === 0 ? "text-ink" : ""}`}>{row.name}</span>
              <span className={`ml-2 truncate ${lit ? "" : "text-ink-faint"}`}>{row.value}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );

  const verdict = (
    <div className="rounded-md border border-line-strong bg-surface">
      <p className="border-b border-line bg-sunken px-5 py-2.5 text-xs text-ink-muted">What TraceroAI tells you</p>
      <dl className="divide-y divide-line">
        {VERDICT.map((line, i) => (
          <div
            key={line.key}
            className="grid grid-cols-[6.5rem_minmax(0,1fr)] gap-3 px-5 py-4"
            style={{ opacity: lineIn(i), transform: `translateY(${(1 - lineIn(i)) * 10}px)` }}
          >
            <dt className="text-sm text-ink-muted">{line.label}</dt>
            <dd className="text-[15px] leading-6">{line.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );

  return (
    <section
      ref={section}
      id="trace-vs-answer"
      aria-labelledby="tva-title"
      data-thread="pin"
      className={`relative scroll-mt-14 ${pinned ? "h-[230vh]" : ""}`}
    >
      <div className={pinned ? "sticky top-14 flex h-[calc(100vh-3.5rem)] items-center" : ""}>
        <div className="mx-auto w-full max-w-[84rem] px-4 py-16 sm:px-8 lg:py-0">
          <div className="focus-in max-w-[46rem]">
            <h2 id="tva-title" className="text-[2.5rem] leading-[1.05] font-bold tracking-[-0.03em] text-balance">
              A trace isn&apos;t an answer
            </h2>
            <p className="mt-4 max-w-[58ch] text-[17px] leading-8 text-ink-muted">
              A trace tells you everything that happened. You still have to read it to find what went wrong. TraceroAI
              reads it and gives you three lines.
            </p>
          </div>
          <div className="mt-10 grid items-start gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:gap-10">
            {pinned ? (
              tree
            ) : (
              <details className="group rounded-md border border-line-strong bg-surface lg:hidden">
                <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-accent">
                  Show the trace these three lines came from ({ROWS.length} lines)
                </summary>
                <div className="border-t border-line">{tree}</div>
              </details>
            )}
            {!pinned && wide && tree}
            {verdict}
          </div>
        </div>
      </div>
    </section>
  );
}
