"use client";

import { useState } from "react";

import { PlaygroundError, tryPlayground, type PlaygroundResult } from "@/lib/api";

import { diagnosisName, diagnosisTone } from "../dashboard/ui";

const TONE = { pass: "bg-pass-soft text-pass", cause: "bg-cause-soft text-cause", warn: "bg-warn-soft text-warn", none: "bg-sunken text-ink-muted" };

const SAMPLES = ["How do I reset my password?", "How long does a refund take?", "Do you offer a free trial?"];

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
      setError(
        err instanceof PlaygroundError && err.rateLimited
          ? err.message
          : "Couldn't reach the API. If it's a hosted demo it may be waking up; try again in half a minute.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded border border-line-strong bg-surface p-5">
      <form
        className="flex flex-col gap-2 sm:flex-row"
        onSubmit={(event) => {
          event.preventDefault();
          run(question);
        }}
      >
        <label htmlFor="playground-question" className="sr-only">
          Question
        </label>
        <input
          id="playground-question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={500}
          placeholder="Ask the demo knowledge base a question"
          className="flex-1 rounded border border-line-strong bg-surface px-3 py-2 text-sm placeholder:text-ink-faint focus:outline-2 focus:outline-accent"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 disabled:cursor-wait disabled:opacity-60"
        >
          {loading ? "Tracing…" : "Trace it"}
        </button>
      </form>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="text-xs text-ink-muted">Try:</span>
        {SAMPLES.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => {
              setQuestion(s);
              run(s);
            }}
            className="rounded-full border border-line-strong px-2.5 py-0.5 text-xs text-ink-muted hover:bg-sunken hover:text-ink"
          >
            {s}
          </button>
        ))}
      </div>

      <div aria-live="polite">
        {error && (
          <p role="alert" className="mt-4 text-sm text-warn">
            {error}
          </p>
        )}

        {result && (
          <div className="replay-in mt-5 space-y-4 border-t border-line pt-4">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <p className="text-sm">
                <span className="text-ink-muted">Question</span> <span className="font-medium">{result.query}</span>
              </p>
              <span className="font-dash-mono text-xs text-ink-muted">{result.latency_ms} ms</span>
            </div>

            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded px-1.5 py-px text-sm font-semibold ${TONE[diagnosisTone(result.diagnosis.label)]}`}>
                  {diagnosisName(result.diagnosis.label)}
                </span>
                <span
                  className={`rounded-[3px] border px-1.5 py-px text-xs ${
                    result.judged_by === "llm_judge" ? "border-ink font-semibold" : "border-dashed border-ink-faint text-ink-muted"
                  }`}
                >
                  {result.judged_by === "llm_judge" ? "Final · LLM judge" : "Preliminary · quick check"}
                </span>
              </div>
              <p className="mt-1.5 text-sm text-ink-muted">{result.diagnosis.reason}</p>
            </div>

            <blockquote className="border-l border-line-strong pl-3 text-sm leading-6">{result.answer}</blockquote>

            <div>
              <p className="mb-2 text-xs font-semibold text-ink-muted">Retrieved context</p>
              <ol className="divide-y divide-line rounded border border-line">
                {result.chunks.map((c, i) => (
                  <li key={i} className="px-3 py-2.5">
                    <div className="flex items-center justify-between gap-3 text-xs">
                      <span className="font-semibold">{c.title}</span>
                      <span className="font-dash-mono text-ink-muted">score {c.score}</span>
                    </div>
                    <p className="mt-1 text-sm leading-6 text-ink-muted">{c.text}</p>
                  </li>
                ))}
              </ol>
            </div>

            <details className="rounded border border-line">
              <summary className="cursor-pointer px-3 py-2 text-xs font-semibold text-ink-muted hover:text-ink">
                Prompt sent to the model
              </summary>
              <pre className="overflow-auto border-t border-line bg-sunken p-3 font-dash-mono text-xs leading-5 whitespace-pre-wrap">
                {result.prompt}
              </pre>
            </details>
          </div>
        )}
      </div>
    </div>
  );
}
