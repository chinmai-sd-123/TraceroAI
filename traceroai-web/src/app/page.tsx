import Link from "next/link";

const features = [
  {
    title: "Trace every RAG answer",
    description:
      "Capture the user question, retrieval step, selected context, prompt, model response, latency, and cost in one timeline.",
  },
  {
    title: "Inspect retrieved evidence",
    description:
      "See which chunks were used, how relevant they were, and whether the answer was actually supported by the retrieved context.",
  },
  {
    title: "Find hallucination causes",
    description:
      "Separate retrieval failures from unsupported generation, noisy context, stale documents, and prompt-level issues.",
  },
  {
    title: "Validate improvements",
    description:
      "Compare fixes across evaluation cases so better prompts, retrievers, and model settings can be tested before release.",
  },
];

const failureTypes = [
  "Unsupported claim",
  "Retrieval miss",
  "Noisy context",
  "Stale source",
  "Weak answer relevance",
  "Latency spike",
];

export default function Home() {
  return (
    <main className="min-h-screen bg-[#050505] text-zinc-100">
      <section className="mx-auto flex min-h-screen max-w-6xl flex-col justify-center px-6 py-20">
        <div className="max-w-4xl">
          <p className="text-sm font-medium uppercase tracking-[0.22em] text-cyan-300">
            TraceroAI
          </p>

          <h1 className="mt-6 text-5xl font-semibold leading-tight md:text-7xl">
            Debug RAG failures before they reach users.
          </h1>

          <p className="mt-6 max-w-3xl text-xl leading-8 text-zinc-300">
            TraceroAI helps AI teams trace, evaluate, and understand why
            retrieval-augmented generation systems produce bad answers.
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/dashboard"
              className="rounded-md bg-cyan-300 px-5 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-200"
            >
              Open Dashboard
            </Link>
            <a
              href="#quickstart"
              className="rounded-md border border-zinc-700 px-5 py-3 text-sm font-semibold text-zinc-100 transition hover:border-zinc-500"
            >
              Quickstart
            </a>
            <a
              href="#product"
              className="rounded-md border border-zinc-700 px-5 py-3 text-sm font-semibold text-zinc-100 transition hover:border-zinc-500"
            >
              Explore Product
            </a>
          </div>
        </div>

        <div className="mt-16 grid gap-4 md:grid-cols-3">
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/70 p-5">
            <p className="text-sm text-zinc-500">Primary use case</p>
            <p className="mt-2 text-lg font-medium">RAG debugging</p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/70 p-5">
            <p className="text-sm text-zinc-500">Core signal</p>
            <p className="mt-2 text-lg font-medium">Groundedness failures</p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/70 p-5">
            <p className="text-sm text-zinc-500">Status</p>
            <p className="mt-2 text-lg font-medium">In active development</p>
          </div>
        </div>
      </section>

      <section id="quickstart" className="border-t border-zinc-800 px-6 py-20">
        <div className="mx-auto max-w-6xl">
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-cyan-300">
            Quickstart
          </p>
          <h2 className="mt-4 max-w-3xl text-3xl font-semibold md:text-4xl">
            Send your first trace in a few lines.
          </h2>
          <p className="mt-5 max-w-3xl leading-8 text-zinc-300">
            TraceroAI is instrumentation, not a chat app. Drop the SDK into any
            RAG pipeline — LangChain, LlamaIndex, or your own — and every answer
            becomes a debuggable trace in the dashboard.
          </p>

          <div className="mt-8 overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950/70">
            <div className="border-b border-zinc-800 px-4 py-2 text-xs text-zinc-500">
              python
            </div>
            <pre className="overflow-auto p-5 text-sm leading-6 text-zinc-300">
              <code>{`from traceroai import TraceroClient

client = TraceroClient(base_url="http://localhost:8000")

client.log_trace(
    query={"original": user_question},
    retrieval={"strategy": "hybrid", "chunks": retrieved_chunks},
    generation={"model": "gpt-4o-mini", "answer": answer},
)`}</code>
            </pre>
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href="/dashboard"
              className="rounded-md bg-cyan-300 px-5 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-200"
            >
              View traces in the dashboard
            </Link>
          </div>
        </div>
      </section>

      <section id="product" className="border-t border-zinc-800 px-6 py-20">
        <div className="mx-auto max-w-6xl">
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-cyan-300">
            Product
          </p>
          <h2 className="mt-4 max-w-3xl text-3xl font-semibold md:text-4xl">
            A debugger for the full RAG answer lifecycle.
          </h2>

          <div className="mt-10 grid gap-5 md:grid-cols-2">
            {features.map((feature) => (
              <div
                key={feature.title}
                className="rounded-lg border border-zinc-800 bg-zinc-900/70 p-6"
              >
                <h3 className="text-lg font-semibold">{feature.title}</h3>
                <p className="mt-3 leading-7 text-zinc-400">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-zinc-800 px-6 py-20">
        <div className="mx-auto grid max-w-6xl gap-10 md:grid-cols-[0.9fr_1.1fr] md:items-center">
          <div>
            <p className="text-sm font-medium uppercase tracking-[0.18em] text-cyan-300">
              Diagnosis
            </p>
            <h2 className="mt-4 text-3xl font-semibold md:text-4xl">
              Bad answers are symptoms. TraceroAI shows the cause.
            </h2>
            <p className="mt-5 leading-8 text-zinc-300">
              A hallucinated answer is not always a model problem. Sometimes the
              retriever missed the right document. Sometimes the context was
              noisy. Sometimes the prompt let the model over-answer. TraceroAI
              is built to separate these failure modes.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {failureTypes.map((type) => (
              <div
                key={type}
                className="rounded-lg border border-zinc-800 bg-zinc-900/70 p-4"
              >
                <p className="font-medium">{type}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="build" className="border-t border-zinc-800 px-6 py-20">
        <div className="mx-auto max-w-6xl">
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-cyan-300">
            Case Study
          </p>
          <h2 className="mt-4 max-w-3xl text-3xl font-semibold md:text-4xl">
            Built as an end-to-end AI engineering project.
          </h2>
          <p className="mt-5 max-w-3xl leading-8 text-zinc-300">
            TraceroAI is being developed to demonstrate production-level AI
            product engineering: tracing, evaluation, reliability workflows,
            backend systems, and a focused developer experience for teams
            working with RAG applications.
          </p>

          <div className="mt-10 rounded-lg border border-zinc-800 bg-zinc-900/70 p-6">
            <p className="text-sm text-zinc-500">Current build focus</p>
            <p className="mt-3 text-xl font-medium">
              Shipping the first working debugger flow: trace a RAG response,
              inspect retrieved chunks, evaluate groundedness, and explain the
              failure.
            </p>
          </div>
        </div>
      </section>

      <footer className="border-t border-zinc-800 px-6 py-10">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 text-sm text-zinc-500 md:flex-row md:items-center md:justify-between">
          <p>TraceroAI</p>
          <p>RAG observability and evaluation infrastructure.</p>
        </div>
      </footer>
    </main>
  );
}