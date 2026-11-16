"use client";

import { useEffect, useState } from "react";

import { useInView, usePrefersReducedMotion } from "./motion";

const TIERS = [
  { name: "Term overlap", when: "On ingest, in the request. No network calls.", final: false },
  { name: "Embedding similarity", when: "In the background, when a provider key is set.", final: false },
  { name: "LLM judge", when: "In the background, when a provider key is set. Overrules the estimates.", final: true },
];

/** The three evaluation tiers, filling in the order they run: the estimates
 * hatched, then the judge's verdict solid. */
export function TierTable() {
  const [ref, seen] = useInView<HTMLDivElement>(0.4);
  const reduced = usePrefersReducedMotion();
  const on = seen || reduced;
  return (
    <div ref={ref} className="overflow-x-auto rounded border border-line">
      <table className="w-full min-w-[34rem] border-collapse text-sm">
        <thead>
          <tr className="border-b border-line-strong bg-sunken text-left text-xs text-ink-muted">
            <th scope="col" className="px-4 py-2 font-medium">Check</th>
            <th scope="col" className="px-4 py-2 font-medium">When it runs</th>
            <th scope="col" className="px-4 py-2 font-medium">Shown as</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {TIERS.map((tier, i) => (
            <tr key={tier.name}>
              <th scope="row" className="px-4 py-3 text-left font-semibold whitespace-nowrap">{tier.name}</th>
              <td className="px-4 py-3 text-ink-muted">{tier.when}</td>
              <td className="px-4 py-3 whitespace-nowrap">
                <span className="inline-flex items-center gap-2">
                  <span className="block h-2.5 w-12 overflow-hidden bg-sunken" aria-hidden="true">
                    <span
                      className={`block h-full text-pass ${tier.final ? "bg-current" : "hatch"} transition-[width] duration-700 ease-out`}
                      style={{ width: on ? "100%" : "0%", transitionDelay: reduced ? "0ms" : `${i * 550}ms` }}
                    />
                  </span>
                  <span
                    className={`rounded-[3px] border px-1.5 py-px text-xs transition-opacity duration-300 ${
                      tier.final ? "border-ink font-semibold" : "border-dashed border-ink-faint text-ink-muted"
                    } ${on ? "opacity-100" : "opacity-0"}`}
                    style={{ transitionDelay: reduced ? "0ms" : `${i * 550 + 500}ms` }}
                  >
                    {tier.final ? "Final" : "Preliminary"}
                  </span>
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const ACCURACY = [
  { tier: "Term overlap", value: 58.1, label: (n: number) => `${n.toFixed(1)}% (68 of 117)` },
  { tier: "Embedding similarity", value: 76.1, label: (n: number) => `${n.toFixed(1)}% (89 of 117)` },
  { tier: "LLM judge", value: 95.7, low: 94.0, label: (n: number) => `${((n * 94.0) / 95.7).toFixed(1)}–${n.toFixed(1)}% over 3 runs`, strong: true },
];

/** Measured accuracy per tier; the bars and figures count up once, on view. */
export function AccuracyTable() {
  const [ref, seen] = useInView<HTMLDivElement>(0.5);
  const reduced = usePrefersReducedMotion();
  const [count, setCount] = useState(0); // 0..1 progress of the count
  const t = reduced ? 1 : count;

  useEffect(() => {
    if (!seen || reduced) return;
    let frame = 0;
    const start = performance.now();
    const step = (now: number) => {
      const p = Math.min(1, (now - start) / 1100);
      setCount(1 - Math.pow(1 - p, 3)); // ease out
      if (p < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [seen, reduced]);

  return (
    <div ref={ref} className="overflow-x-auto rounded border border-line">
      <table className="w-full min-w-[22rem] border-collapse text-sm">
        <caption className="sr-only">Diagnosis accuracy by evaluation tier</caption>
        <thead>
          <tr className="border-b border-line-strong bg-sunken text-left text-xs text-ink-muted">
            <th scope="col" className="px-4 py-2 font-medium">Tier</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Right diagnosis</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {ACCURACY.map((row) => (
            <tr key={row.tier}>
              <th scope="row" className="px-4 py-3 text-left font-semibold whitespace-nowrap">{row.tier}</th>
              <td className="px-4 py-3">
                <div className="flex items-center justify-end gap-4">
                  <span className="relative hidden h-2 w-56 bg-sunken sm:block" aria-hidden="true">
                    <span className={`block h-2 ${row.strong ? "bg-accent" : "bg-ink-muted/45"}`} style={{ width: `${row.value * t}%` }} />
                    {[25, 50, 75].map((tick) => (
                      <span key={tick} className="absolute top-0 h-2 w-px bg-surface" style={{ left: `${tick}%` }} />
                    ))}
                  </span>
                  {/* Screen readers get the final figure, not the count. */}
                  <span className={`w-44 text-right ${row.strong ? "font-semibold" : "text-ink-muted"}`}>
                    <span aria-hidden="true">{row.label(row.value * (t === 0 ? 0 : t))}</span>
                    <span className="sr-only">{row.label(row.value)}</span>
                  </span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Per label, from docs/evaluation-benchmark.md (run of 2026-11-13). Judge
// figures are from the first of its three runs.
const PER_LABEL = [
  { label: "Healthy answer", cases: 22, lexical: "1.00 / 0.14", embedding: "0.93 / 0.64", judge: "0.95 / 0.95" },
  { label: "Correct refusal", cases: 18, lexical: "0.56 / 1.00", embedding: "0.94 / 0.94", judge: "1.00 / 0.94" },
  { label: "Retrieval miss", cases: 20, lexical: "0.53 / 1.00", embedding: "1.00 / 0.85", judge: "1.00 / 0.95" },
  { label: "Unsupported claim", cases: 21, lexical: "0.92 / 0.52", embedding: "0.77 / 0.62", judge: "0.81 / 1.00" },
  { label: "Wrong answer", cases: 36, lexical: "0.73 / 0.44", embedding: "0.97 / 0.78", judge: "0.97 / 0.89" },
];

/** Precision and recall per diagnosis label, for each tier, behind a toggle. */
export function PerLabelTable() {
  return (
    <details className="group mt-3 rounded border border-line">
      <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium text-accent">
        Precision and recall per label
      </summary>
      <div className="overflow-x-auto border-t border-line">
        <table className="w-full min-w-[34rem] border-collapse text-sm">
          <caption className="px-4 pt-3 text-left text-xs text-ink-muted">
            Precision is how often a label is right when it&apos;s given; recall is how many of the cases with that label
            it finds. Judge figures are from the first of three runs.
          </caption>
          <thead>
            <tr className="border-y border-line-strong bg-sunken text-left text-xs text-ink-muted">
              <th scope="col" className="px-4 py-2 font-medium">Label</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Cases</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Term overlap P / R</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Embedding P / R</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Judge P / R</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line font-dash-mono text-[12.5px]">
            {PER_LABEL.map((row) => (
              <tr key={row.label}>
                <th scope="row" className="px-4 py-2.5 text-left font-dash font-semibold text-sm">{row.label}</th>
                <td className="px-4 py-2.5 text-right">{row.cases}</td>
                <td className="px-4 py-2.5 text-right text-ink-muted">{row.lexical}</td>
                <td className="px-4 py-2.5 text-right text-ink-muted">{row.embedding}</td>
                <td className="px-4 py-2.5 text-right font-medium">{row.judge}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
