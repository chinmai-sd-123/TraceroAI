import type { Metadata } from "next";
import Link from "next/link";

import { CodeTabs } from "./code-tabs";
import { Playground } from "./playground";
import { SectionNav } from "./section-nav";

export const metadata: Metadata = {
  title: "Docs & Examples | TraceroAI",
  description:
    "Install the TraceroAI SDK, instrument any RAG pipeline, add self-healing recovery, and try a live query against the demo.",
};

const INSTALL = `pip install traceroai`;

const TRACE_TABS = [
  {
    label: "Context manager",
    code: `from traceroai import TraceroClient

client = TraceroClient(
    base_url="https://traceroai.onrender.com",
    api_key="your_project_key",   # optional
)

with client.trace("How long does a refund take?") as t:
    chunks = retrieve(query)                 # your retriever
    t.log_retrieval(chunks, strategy="hybrid", config={"top_k": 3})
    t.log_prompt(prompt_text, version="grounded_v1")   # optional
    answer = generate(prompt, chunks)        # your LLM
    t.log_generation(answer, model="gpt-4o-mini", provider="openai")

print(t.trace_id)   # the sent trace id (None if sending failed)`,
  },
  {
    label: "Decorator",
    code: `from traceroai import TraceroClient

client = TraceroClient(base_url="https://traceroai.onrender.com")

@client.traced(model="gpt-4o-mini", strategy="hybrid")
def answer(query: str):
    chunks = retrieve(query)
    return generate(query, chunks), chunks   # must return (answer, chunks)

answer("What is the maximum upload size?")   # traced automatically`,
  },
  {
    label: "Low-level",
    code: `client.log_trace(
    query={"original": question},
    retrieval={"strategy": "hybrid", "chunks": chunks},
    generation={"model": "gpt-4o-mini", "answer": answer},
    prompt={"content": prompt},        # optional
    latency={"total_ms": 1171},        # optional
    project={"project_id": "my-app"},  # optional
    metadata={"env": "prod"},          # optional
)
# Note: evaluations + diagnosis are computed server-side, so you don't send them.`,
  },
];

const RECOVERY_CODE = `pip install "traceroai[recovery]"`;

const RECOVERY_TABS = [
  {
    label: "Run the agent",
    code: `from traceroai import TraceroClient
from traceroai.recovery import RecoveryAgent

agent = RecoveryAgent(
    client,
    retrieve=my_retrieve,    # (query, top_k) -> list[chunk dict]
    generate=my_generate,    # (query, context) -> answer str
    max_attempts=3,
)

result = agent.run("How long does a refund take?")
result["answer"]      # final answer
result["diagnosis"]   # final diagnosis label
result["attempts"]    # how many tries it took
result["succeeded"]   # reached a healthy answer?
result["trace_ids"]   # the retry chain (one trace per attempt)
result["deep_eval"]   # final LLM-judge verdict (or None if pending)`,
  },
  {
    label: "Load your own docs",
    code: `from langchain_text_splitters import RecursiveCharacterTextSplitter

# TraceroAI does not load documents — your retriever does. Load any format
# (.txt, .md, .pdf, a vector DB...), split, embed, and return chunks from
# retrieve(query, top_k). See examples/recovery-agent for the full flow.
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)
chunks = splitter.split_text(open("policy.md").read())`,
  },
];

// Server-computed diagnosis: every trace is reduced to exactly one of these.
const LABELS: Array<{ label: string; meaning: string; tone: string }> = [
  { label: "healthy_answer", meaning: "Retrieval, grounding, and relevance all pass.", tone: "text-emerald-300" },
  { label: "correct_refusal", meaning: "The model rightly declined — the context didn't support an answer.", tone: "text-sky-300" },
  { label: "retrieval_miss", meaning: "Retrieved context doesn't match the query.", tone: "text-amber-300" },
  { label: "unsupported_claim", meaning: "The answer asserts things the context doesn't support.", tone: "text-red-300" },
  { label: "wrong_answer", meaning: "The answer doesn't address the query.", tone: "text-red-300" },
  { label: "needs_review", meaning: "Mixed signals — flagged for a human.", tone: "text-zinc-300" },
];

const TRACE_METHODS: Array<{ sig: string; body: string }> = [
  { sig: "client.trace(query, *, rewritten=, project=, metadata=)", body: "Open a tracing context manager. Auto-times the block and sends on exit." },
  { sig: "t.log_retrieval(chunks, *, strategy=, config=)", body: "Record retrieved chunks (list of dicts, each with at least a `text` field)." },
  { sig: "t.log_prompt(content, *, version=, template_name=)", body: "Optional — record the prompt sent to the model." },
  { sig: "t.log_generation(answer, *, model, provider=, temperature=)", body: "Record the generated answer. `model` is required." },
  { sig: "client.traced(*, model, strategy='vector')", body: "Decorator for a function returning (answer, chunks)." },
  { sig: "client.log_trace(*, query, retrieval, generation, ...)", body: "Low-level: assemble and send a whole trace in one call." },
  { sig: "client.get_trace(trace_id)", body: "Fetch a stored trace back — diagnosis + evaluations included." },
];

const NAV: [string, string][] = [
  ["install", "Install"],
  ["try", "Try it live"],
  ["trace", "Send traces"],
  ["reference", "SDK reference"],
  ["diagnosis", "Diagnosis labels"],
  ["recovery", "Self-healing recovery"],
  ["experiments", "Experiment runs"],
  ["auth", "Auth & projects"],
];

export default function DocsPage() {
  return (
    <main className="min-h-screen bg-[#050505] text-zinc-100">
      <div className="border-b border-zinc-800">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link href="/" className="text-sm font-semibold tracking-wide">
            TraceroAI
          </Link>
          <nav className="flex gap-1 text-sm">
            <Link href="/docs" className="rounded-md px-3 py-2 text-zinc-100">
              Docs
            </Link>
            <Link
              href="/dashboard"
              className="rounded-md px-3 py-2 text-zinc-400 transition hover:text-zinc-100"
            >
              Dashboard
            </Link>
          </nav>
        </div>
      </div>

      <div className="mx-auto max-w-6xl gap-10 px-6 py-12 lg:grid lg:grid-cols-[200px_1fr]">
        {/* Sticky sidebar nav with scroll-spy */}
        <aside className="hidden lg:block">
          <SectionNav items={NAV} />
        </aside>

        <div className="min-w-0">
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-cyan-300">
            Docs &amp; Examples
          </p>
          <h1 className="mt-4 text-4xl font-semibold md:text-5xl">
            Instrument any RAG pipeline.
          </h1>
          <p className="mt-5 max-w-2xl text-lg leading-8 text-zinc-300">
            TraceroAI is instrumentation, not a chat app. Add the SDK and every
            answer becomes a debuggable trace — retrieval, prompt, answer,
            evaluations, and an automatic diagnosis — plus an optional agent that
            retries the stage that failed.
          </p>

          {/* Install */}
          <section id="install" className="mt-14 scroll-mt-12">
            <h2 className="text-2xl font-semibold">Install</h2>
            <div className="mt-4 overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950/70">
              <div className="border-b border-zinc-800 px-4 py-2 text-xs text-zinc-500">
                bash
              </div>
              <pre className="p-5 text-sm text-zinc-300">
                <code>{INSTALL}</code>
              </pre>
            </div>
            <p className="mt-3 text-sm text-zinc-400">
              The only base dependency is <code className="text-zinc-300">httpx</code>.
              Telemetry is <span className="text-zinc-300">best-effort</span> — if the
              API is unreachable, the SDK warns and continues; it never breaks your app.
            </p>
          </section>

          {/* Try it live */}
          <section id="try" className="mt-16 scroll-mt-12">
            <h2 className="text-2xl font-semibold">Try it live</h2>
            <p className="mt-2 text-sm text-zinc-400">
              Ask the built-in demo knowledge base a question. It runs real retrieval
              + evaluation on the live API and shows the trace below — no signup, no key.
            </p>
            <div className="mt-5">
              <Playground />
            </div>
          </section>

          {/* Send traces */}
          <section id="trace" className="mt-16 scroll-mt-12">
            <h2 className="text-2xl font-semibold">Send traces</h2>
            <p className="mt-2 text-sm text-zinc-400">
              Three styles, from most explicit to most automatic — they all produce
              the same kind of trace.
            </p>
            <div className="mt-4">
              <CodeTabs tabs={TRACE_TABS} />
            </div>
          </section>

          {/* SDK reference */}
          <section id="reference" className="mt-16 scroll-mt-12">
            <h2 className="text-2xl font-semibold">SDK reference</h2>
            <p className="mt-2 text-sm text-zinc-400">
              The full public surface of <code className="text-zinc-300">TraceroClient</code>.
            </p>
            <div className="mt-4 divide-y divide-zinc-800 overflow-hidden rounded-lg border border-zinc-800">
              {TRACE_METHODS.map((m) => (
                <div key={m.sig} className="bg-zinc-900/40 p-4">
                  <code className="text-sm text-cyan-200">{m.sig}</code>
                  <p className="mt-1.5 text-sm text-zinc-400">{m.body}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Diagnosis labels */}
          <section id="diagnosis" className="mt-16 scroll-mt-12">
            <h2 className="text-2xl font-semibold">Diagnosis labels</h2>
            <p className="mt-2 text-sm text-zinc-400">
              The server evaluates every trace (embedding-cosine relevance +
              groundedness, plus an async LLM judge) and reduces it to one label:
            </p>
            <div className="mt-4 divide-y divide-zinc-800 overflow-hidden rounded-lg border border-zinc-800">
              {LABELS.map((l) => (
                <div key={l.label} className="flex flex-col gap-1 bg-zinc-900/40 p-4 sm:flex-row sm:items-center sm:gap-4">
                  <code className={`shrink-0 text-sm font-medium ${l.tone}`}>{l.label}</code>
                  <p className="text-sm text-zinc-400">{l.meaning}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Recovery */}
          <section id="recovery" className="mt-16 scroll-mt-12">
            <h2 className="text-2xl font-semibold">Self-healing recovery</h2>
            <p className="mt-2 max-w-2xl text-sm text-zinc-400">
              An optional LangGraph agent that <span className="text-zinc-200">fixes its own bad answers</span>:
              it evaluates each attempt and retries the stage that failed — re-retrieving
              with more context on a <code className="text-amber-300">retrieval_miss</code>,
              re-generating with a stricter prompt on an{" "}
              <code className="text-red-300">unsupported_claim</code> — until the answer is
              healthy or it escalates to review (bounded by <code className="text-zinc-300">max_attempts</code>).
            </p>
            <div className="mt-4 overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950/70">
              <div className="border-b border-zinc-800 px-4 py-2 text-xs text-zinc-500">
                bash
              </div>
              <pre className="p-5 text-sm text-zinc-300">
                <code>{RECOVERY_CODE}</code>
              </pre>
            </div>
            <div className="mt-3">
              <CodeTabs tabs={RECOVERY_TABS} />
            </div>
          </section>

          {/* Experiment runs */}
          <section id="experiments" className="mt-16 scroll-mt-12">
            <h2 className="text-2xl font-semibold">Experiment runs</h2>
            <p className="mt-2 max-w-2xl text-sm text-zinc-400">
              Compare pipeline configs (top_k, prompt, model) against a labeled dataset.
              The harness replays every case across each variant, grades the answers with
              the LLM judge, and recommends a winner — A/B testing for RAG. Results show
              up under <Link href="/dashboard/eval-runs" className="text-cyan-300 hover:underline">Eval Runs</Link>.
            </p>
            <div className="mt-4 overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950/70">
              <div className="border-b border-zinc-800 px-4 py-2 text-xs text-zinc-500">
                bash
              </div>
              <pre className="overflow-auto p-5 text-sm leading-6 text-zinc-300">
                <code>{`# from services/api — runs the experiment and posts the result
python -m app.eval_runner \\
    --dataset support_faq_v1 \\
    --project my-app \\
    --post \\
    --api-url https://traceroai.onrender.com`}</code>
              </pre>
            </div>
            <p className="mt-3 text-sm text-zinc-400">
              Each run records, per variant: accuracy (correct vs. expected answers,
              judged by the LLM) and average latency. The recommended winner is the
              highest-accuracy variant.
            </p>
          </section>

          {/* Auth */}
          <section id="auth" className="mt-16 scroll-mt-12">
            <h2 className="text-2xl font-semibold">Auth &amp; projects</h2>
            <p className="mt-2 max-w-2xl text-sm text-zinc-400">
              Pass a project API key and the server stamps every trace with that
              project, so the dashboard can filter to it. The key is optional — without
              one, traces use whatever <code className="text-zinc-300">project_id</code> you
              pass. Reads are open, so anyone can browse the demo.
            </p>
            <div className="mt-4 overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950/70">
              <pre className="overflow-auto p-5 text-sm leading-6 text-zinc-300">
                <code>{`client = TraceroClient(
    base_url="https://traceroai.onrender.com",
    api_key="your_project_key",
)`}</code>
              </pre>
            </div>
          </section>

          <section className="mt-16 flex flex-wrap gap-3">
            <Link
              href="/dashboard"
              className="rounded-md bg-cyan-300 px-5 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-200"
            >
              Open the Dashboard
            </Link>
            <a
              href="https://pypi.org/project/traceroai/"
              className="rounded-md border border-zinc-700 px-5 py-3 text-sm font-semibold text-zinc-100 transition hover:border-zinc-500"
            >
              View on PyPI
            </a>
          </section>
        </div>
      </div>
    </main>
  );
}
