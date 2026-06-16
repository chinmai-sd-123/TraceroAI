"use client";

import { useState } from "react";

import { PlaygroundError, tryPlayground, type PlaygroundResult } from "@/lib/api";

const DIAGNOSIS_STYLES: Record<string, string> = {
  healthy_answer: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  correct_refusal: "border-sky-500/30 bg-sky-500/10 text-sky-300",
  retrieval_miss: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  unsupported_claim: "border-red-500/30 bg-red-500/10 text-red-300",
  wrong_answer: "border-red-500/30 bg-red-500/10 text-red-300",
  needs_review: "border-zinc-500/30 bg-zinc-500/10 text-zinc-300",
};

const SAMPLES = [
  "How do I reset my password?",
  "How long does a refund take?",
  "Do you offer a free trial?",
];

export function Playground() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PlaygroundResult | null>(null);

  async function run(q: string) {
    const text = q.trim();
    if (!text) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await tryPlayground(text));
    } catch (err) {
      if (err instanceof PlaygroundError && err.rateLimited) {
        setError(err.message);
      } else {
        setError("Couldn't reach the live API (it may be waking up — try again in ~30s).");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run(question)}
          placeholder="Ask the demo RAG a question…"
          className="flex-1 rounded-md border border-zinc-800 bg-zinc-950/70 px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-cyan-500/50 focus:outline-none"
        />
        <button
          type="button"
          onClick={() => run(question)}
          disabled={loading}
          className="rounded-md bg-cyan-300 px-5 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-200 disabled:opacity-50"
        >
          {loading ? "Tracing…" : "Trace it"}
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <span className="text-xs text-zinc-600">Try:</span>
        {SAMPLES.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => {
              setQuestion(s);
              run(s);
            }}
            className="rounded-full border border-zinc-800 px-3 py-1 text-xs text-zinc-400 transition hover:border-zinc-600 hover:text-zinc-200"
          >
            {s}
          </button>
        ))}
      </div>

      {error && <p className="mt-4 text-sm text-amber-400">{error}</p>}

      {result && (
        <div className="mt-6 space-y-4">
          <div className="flex items-center justify-between gap-4">
            <p className="text-sm text-zinc-400">
              Answer:{" "}
              <span className="text-zinc-100">{result.answer}</span>
            </p>
            <span
              className={`shrink-0 rounded-md border px-3 py-1 text-xs font-medium ${
                DIAGNOSIS_STYLES[result.diagnosis.label] ?? DIAGNOSIS_STYLES.needs_review
              }`}
            >
              {result.diagnosis.label.replaceAll("_", " ")}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <span
              className={`rounded px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
                result.judged_by === "llm_judge"
                  ? "bg-cyan-500/15 text-cyan-300"
                  : "bg-zinc-700/40 text-zinc-400"
              }`}
            >
              {result.judged_by === "llm_judge"
                ? "LLM judge (deep eval)"
                : "deterministic (fast)"}
            </span>
            <p className="text-xs leading-5 text-zinc-500">{result.diagnosis.reason}</p>
          </div>

          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
              Retrieved context
            </p>
            <div className="space-y-2">
              {result.chunks.map((c, i) => (
                <div
                  key={i}
                  className="rounded-md border border-zinc-800 bg-zinc-950/60 p-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-zinc-300">{c.title}</span>
                    <span className="font-mono text-xs text-zinc-500">
                      score {c.score}
                    </span>
                  </div>
                  <p className="mt-1 text-sm leading-6 text-zinc-400">{c.text}</p>
                </div>
              ))}
            </div>
          </div>

          <p className="text-xs text-zinc-600">
            ↑ This is a real trace, evaluated live by the deterministic pipeline.
            Send your own with the SDK and it appears in the dashboard.
          </p>
        </div>
      )}
    </div>
  );
}
