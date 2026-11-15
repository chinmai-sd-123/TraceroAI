"use client";

import { useEffect, useState } from "react";

import { useInView, usePrefersReducedMotion } from "./motion";

const STAGES = [
  { name: "Retrieval", question: "Did the retrieved context match the question?" },
  { name: "Grounding", question: "Is every claim supported by that context?" },
  { name: "Answer", question: "Does the answer address the question?" },
];

const FAILURES = [
  {
    label: "Retrieval miss",
    stage: 0,
    what: "The documents that answer the question weren't retrieved, so the model had nothing right to work from.",
    example: "Asked about annual-plan refunds; only the monthly billing pages came back.",
    fix: "Retrieve more, or fix the index.",
  },
  {
    label: "Unsupported claim",
    stage: 1,
    what: "The right documents came back, but the answer says something they don't.",
    example: '"Refunded within 10 days" when the policy only says 5 to 7 business days after approval.',
    fix: "Regenerate with a stricter prompt.",
  },
  {
    label: "Wrong answer",
    stage: 2,
    what: "Grounded in the context, but it answers a different question, or refuses one it could answer.",
    example: 'Asked for the refund policy, which the context covered; the model said "I don\'t know."',
    fix: "Change the prompt or the model.",
  },
];

/** Where a RAG answer can break. Pick a failure (or let it cycle) and the
 * probe runs the pipeline, stopping at the stage that broke. */
export function PipelineExplorer() {
  const reduced = usePrefersReducedMotion();
  const [ref, inView] = useInView<HTMLDivElement>(0.4);
  const [active, setActive] = useState(0);
  const [hovering, setHovering] = useState(false);
  const [run, setRun] = useState(0); // restarts the probe animation
  const failure = FAILURES[active];

  useEffect(() => {
    if (!inView || reduced || hovering) return;
    const id = setTimeout(() => {
      setActive((a) => (a + 1) % FAILURES.length);
      setRun((r) => r + 1);
    }, 5200);
    return () => clearTimeout(id);
  }, [inView, reduced, hovering, active]);

  // Probe position: 0 = query, then one step per stage, stopping at the failure.
  const stop = failure.stage + 1;

  return (
    <div ref={ref} onPointerEnter={() => setHovering(true)} onPointerLeave={() => setHovering(false)} onFocus={() => setHovering(true)} onBlur={() => setHovering(false)}>
      <div role="tablist" aria-label="Failure types" className="flex flex-wrap gap-2">
        {FAILURES.map((f, i) => (
          <button
            key={f.label}
            type="button"
            role="tab"
            aria-selected={i === active}
            onClick={() => {
              setActive(i);
              setRun((r) => r + 1);
            }}
            className={`rounded border px-3 py-1.5 text-sm ${
              i === active ? "border-cause bg-cause-soft font-semibold text-cause" : "border-line-strong bg-surface text-ink hover:bg-sunken"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* The track: query, then the three stages. */}
      <div className="relative mt-8 hidden h-10 md:block" aria-hidden="true">
        <div className="absolute inset-x-[4%] top-1/2 h-px bg-line-strong" />
        {[0, 1, 2, 3].map((node) => {
          const passed = inView && node > 0 && node < stop;
          const broke = inView && node === stop;
          return (
            <span
              key={node}
              className={`absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 transition-colors duration-300 ${
                broke ? "border-cause bg-cause" : passed ? "border-pass bg-pass" : "border-line-strong bg-surface"
              }`}
              style={{ left: `${4 + node * 30.67}%`, transitionDelay: inView && !reduced ? `${node * 380}ms` : "0ms" }}
            >
              {broke && !reduced && <span key={run} className="probe-ring absolute -inset-1.5 rounded-full border-2 border-cause" />}
            </span>
          );
        })}
        <span
          key={`probe-${run}`}
          className="probe absolute top-1/2 size-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent"
          style={{
            ["--probe-to" as string]: `${4 + stop * 30.67}%`,
            left: reduced || !inView ? `${4 + stop * 30.67}%` : undefined,
            animationDuration: `${stop * 380}ms`,
          }}
        />
        <span className="absolute top-full mt-1 text-xs text-ink-muted" style={{ left: "4%", transform: "translateX(-50%)" }}>
          Query
        </span>
      </div>

      <ol className="mt-2 grid border border-line-strong md:mt-6 md:grid-cols-3" aria-label="The stages TraceroAI checks">
        {STAGES.map((stage, i) => {
          const broke = i === failure.stage;
          const passed = i < failure.stage;
          return (
            <li
              key={stage.name}
              className={`relative border-line px-5 pt-5 pb-4 transition-colors duration-300 max-md:[&:not(:first-child)]:border-t md:[&:not(:first-child)]:border-l ${
                broke ? "bg-cause-soft" : ""
              }`}
            >
              <span
                className={`absolute inset-x-0 top-0 h-[3px] transition-colors duration-300 ${broke ? "bg-cause" : passed ? "bg-pass" : "bg-line-strong"}`}
                aria-hidden="true"
              />
              <p className="flex items-baseline justify-between gap-3 font-semibold">
                <span>
                  <span className="mr-1.5 font-medium text-ink-faint">{i + 1}</span>
                  {stage.name}
                </span>
                <span className={`text-sm ${broke ? "text-cause" : passed ? "text-pass" : "text-ink-faint"}`}>
                  {broke ? "Probable cause" : passed ? "Passed" : "Not the cause"}
                </span>
              </p>
              <p className="mt-1 text-sm text-ink-muted">{stage.question}</p>
              {broke && (
                <div key={`${active}-${run}`} className="replay-in mt-4">
                  <p>
                    <span className="rounded bg-surface px-1.5 py-px text-sm font-semibold text-cause">{failure.label}</span>
                  </p>
                  <p className="mt-2 text-sm">{failure.what}</p>
                  <p className="mt-2 text-sm text-ink-muted">
                    <span className="font-medium text-ink">For example:</span> {failure.example}
                  </p>
                  <p className="mt-2 text-sm text-ink-muted">
                    <span className="font-medium text-ink">Usual fix:</span> {failure.fix}
                  </p>
                </div>
              )}
            </li>
          );
        })}
      </ol>

      <dl className="mt-4 grid gap-x-8 gap-y-2 text-sm sm:grid-cols-3">
        <div>
          <dt className="font-semibold text-pass">Healthy answer</dt>
          <dd className="text-ink-muted">All three checks passed.</dd>
        </div>
        <div>
          <dt className="font-semibold text-pass">Correct refusal</dt>
          <dd className="text-ink-muted">The documents don&apos;t cover it, and the model said so.</dd>
        </div>
        <div>
          <dt className="font-semibold text-warn">Needs review</dt>
          <dd className="text-ink-muted">The checks couldn&apos;t decide; a person should look.</dd>
        </div>
      </dl>
    </div>
  );
}
