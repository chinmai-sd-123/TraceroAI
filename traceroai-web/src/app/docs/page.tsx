import type { Metadata } from "next";
import Link from "next/link";

import { CodeTabs } from "./code-tabs";
import { Playground } from "./playground";

export const metadata: Metadata = {
  title: "Docs & Examples | TraceroAI",
  description:
    "Install the TraceroAI SDK, instrument any RAG pipeline in a few lines, and try a live query against the demo.",
};

const INSTALL = `pip install traceroai`;

const TABS = [
  {
    label: "Context manager",
    code: `from traceroai import TraceroClient

client = TraceroClient(
    base_url="https://traceroai.onrender.com",
    api_key="your_project_key",
)

with client.trace("How long does a refund take?") as t:
    chunks = retrieve(query)              # your retriever
    t.log_retrieval(chunks, strategy="hybrid")
    answer = generate(prompt, chunks)     # your LLM
    t.log_generation(answer, model="gpt-4o-mini")
# auto-times the block and sends the trace on exit`,
  },
  {
    label: "Decorator",
    code: `from traceroai import TraceroClient

client = TraceroClient(base_url="https://traceroai.onrender.com")

@client.traced(model="gpt-4o-mini", strategy="hybrid")
def answer(query: str):
    chunks = retrieve(query)
    return generate(query, chunks), chunks   # (answer, chunks)

answer("What is the maximum upload size?")   # traced automatically`,
  },
  {
    label: "Low-level",
    code: `client.log_trace(
    query={"original": question},
    retrieval={"strategy": "hybrid", "chunks": chunks},
    generation={"model": "gpt-4o-mini", "answer": answer},
)`,
  },
];

const STEPS = [
  {
    n: "01",
    title: "Install the SDK",
    body: "One dependency. Works in any Python RAG project — LangChain, LlamaIndex, or your own.",
  },
  {
    n: "02",
    title: "Wrap your RAG call",
    body: "Log retrieval + generation inside a `client.trace(...)` block (or a decorator). Latency is timed automatically.",
  },
  {
    n: "03",
    title: "Debug in the dashboard",
    body: "Every answer becomes a trace with retrieved chunks, evaluations, and a diagnosis — so you see why a bad answer was bad.",
  },
];

export default function DocsPage() {
  return (
    <main className="min-h-screen bg-[#050505] text-zinc-100">
      <div className="border-b border-zinc-800">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
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

      <div className="mx-auto max-w-5xl px-6 py-16">
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-cyan-300">
          Docs &amp; Examples
        </p>
        <h1 className="mt-4 text-4xl font-semibold md:text-5xl">
          Monitor any RAG app in a few lines.
        </h1>
        <p className="mt-5 max-w-2xl text-lg leading-8 text-zinc-300">
          TraceroAI is instrumentation, not a chat app. Add the SDK to your RAG
          pipeline and every answer becomes a debuggable trace — retrieval,
          prompt, answer, evaluations, and an automatic diagnosis.
        </p>

        {/* Live try-it */}
        <section className="mt-14">
          <h2 className="text-2xl font-semibold">Try it live</h2>
          <p className="mt-2 text-sm text-zinc-400">
            Ask the built-in demo knowledge base a question. It runs real
            retrieval + evaluation on the live API and shows the trace below —
            no signup, no key.
          </p>
          <div className="mt-5">
            <Playground />
          </div>
        </section>

        {/* Quickstart */}
        <section className="mt-16">
          <h2 className="text-2xl font-semibold">Quickstart</h2>
          <div className="mt-5 overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950/70">
            <div className="border-b border-zinc-800 px-4 py-2 text-xs text-zinc-500">
              install
            </div>
            <pre className="p-5 text-sm text-zinc-300">
              <code>{INSTALL}</code>
            </pre>
          </div>
          <p className="mt-5 text-sm text-zinc-400">
            Then instrument your pipeline — pick the style you like:
          </p>
          <div className="mt-3">
            <CodeTabs tabs={TABS} />
          </div>
        </section>

        {/* How it works */}
        <section className="mt-16">
          <h2 className="text-2xl font-semibold">How it works</h2>
          <div className="mt-6 grid gap-5 md:grid-cols-3">
            {STEPS.map((s) => (
              <div
                key={s.n}
                className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-5"
              >
                <p className="font-mono text-sm text-cyan-300">{s.n}</p>
                <p className="mt-2 font-semibold">{s.title}</p>
                <p className="mt-2 text-sm leading-6 text-zinc-400">{s.body}</p>
              </div>
            ))}
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
    </main>
  );
}
