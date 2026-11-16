import type { ReactNode } from "react";

import { DIAGNOSIS_NAMES, causeStage, diagnosisTone } from "@/app/dashboard/ui";
import { Playground } from "@/app/docs/playground";
import { publicApiConfigured } from "@/lib/site-mode";

// Blocks the docs' MDX pages use beyond plain markdown.

/** An aside: something to know before acting on the text around it. */
export function Note({ children }: { children?: ReactNode }) {
  return (
    <aside className="mt-5 max-w-[70ch] rounded border-l-[3px] border-accent bg-accent-soft/60 px-4 py-3 text-sm leading-6 text-ink [&_p]:mt-0 [&_p+p]:mt-2 [&_p]:text-ink">
      {children}
    </aside>
  );
}

const TONE = {
  pass: "bg-pass-soft text-pass",
  cause: "bg-cause-soft text-cause",
  warn: "bg-warn-soft text-warn",
  none: "bg-sunken text-ink-muted",
};
const STAGE_NAMES = { retrieval: "Retrieval", grounding: "Grounding", answer: "Answer" };

const DIAGNOSES: Array<{ label: keyof typeof DIAGNOSIS_NAMES; meaning: string }> = [
  { label: "healthy_answer", meaning: "Retrieval, grounding and the answer all passed." },
  { label: "correct_refusal", meaning: "The context didn't cover the question, and the model said so." },
  { label: "retrieval_miss", meaning: "The retrieved context doesn't match the question." },
  { label: "low_context_relevance", meaning: "The context is only loosely related to the question." },
  { label: "unsupported_claim", meaning: "The answer states something the context doesn't support." },
  { label: "wrong_answer", meaning: "Grounded, but it doesn't answer the question, or it refuses one it could answer." },
  { label: "needs_review", meaning: "The checks couldn't decide; a person should look." },
];

/** Every diagnosis, with the stage it blames, drawn as the dashboard draws it. */
export function DiagnosisTable() {
  return (
    <div className="mt-5 overflow-x-auto rounded border border-line">
      <table className="w-full min-w-[34rem] border-collapse text-sm">
        <thead>
          <tr className="border-b border-line-strong bg-sunken text-left text-xs text-ink-muted">
            <th scope="col" className="px-4 py-2 font-medium">Diagnosis</th>
            <th scope="col" className="px-4 py-2 font-medium">Stage it blames</th>
            <th scope="col" className="px-4 py-2 font-medium">Meaning</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {DIAGNOSES.map((d) => {
            const stage = causeStage(d.label);
            return (
              <tr key={d.label}>
                <th scope="row" className="px-4 py-3 text-left font-normal whitespace-nowrap">
                  <span className={`rounded px-1.5 py-px text-sm font-semibold ${TONE[diagnosisTone(d.label)]}`}>
                    {DIAGNOSIS_NAMES[d.label]}
                  </span>
                  <span className="mt-1 block font-dash-mono text-xs text-ink-muted">{d.label}</span>
                </th>
                <td className="px-4 py-3 text-ink-muted">{stage ? STAGE_NAMES[stage] : "None"}</td>
                <td className="px-4 py-3 text-ink-muted">{d.meaning}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** The live playground when this site has an API behind it; otherwise how to run one. */
export function TryPlayground() {
  if (publicApiConfigured()) {
    return (
      <div className="mt-5">
        <Playground />
      </div>
    );
  }
  return (
    <Note>
      <p>
        This site has no API behind it, so the playground is off here. Run the stack (see Quickstart), set{" "}
        <code>TRACEROAI_PLAYGROUND_ENABLED=true</code> on the API, and open this page at{" "}
        <code>http://localhost:3000/docs/try-it</code>.
      </p>
    </Note>
  );
}
