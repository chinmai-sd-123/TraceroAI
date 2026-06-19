import Link from "next/link";

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "TraceroAI",
  applicationCategory: "DeveloperApplication",
  operatingSystem: "Any",
  description:
    "Debug RAG failures before they reach users. TraceroAI traces, evaluates, and diagnoses retrieval-augmented generation pipelines with an LLM-as-judge and a self-healing recovery agent.",
  url: "https://www.traceroai.tech",
  offers: {
    "@type": "Offer",
    price: "0",
    priceCurrency: "USD",
    description: "Open-source RAG observability platform",
  },
  featureList: [
    "RAG trace capture (query, retrieval, generation, latency)",
    "Two-tier evaluation: embedding cosine + LLM-as-judge groundedness",
    "Self-healing recovery agent (LangGraph)",
    "A/B experiment harness for RAG pipeline configs",
    "Python SDK: pip install traceroai",
  ],
};

const features = [
  {
    title: "Trace every RAG answer",
    description:
      "Capture the question, retrieval step, selected context, prompt, model response, and latency in one timeline — via a drop-in Python SDK.",
  },
  {
    title: "Two-tier evaluation",
    description:
      "Fast embedding-cosine relevance scores every trace; an LLM-as-judge runs claim-level groundedness asynchronously. Each answer is reduced to a single diagnosis.",
  },
  {
    title: "Self-healing recovery",
    description:
      "A LangGraph agent retries the stage that failed — re-retrieving on a retrieval miss, re-generating with a stricter prompt on an unsupported claim — until the answer is healthy.",
  },
  {
    title: "Experiment harness",
    description:
      "Replay a labeled dataset across pipeline configs (top_k, prompt, model), grade each with an LLM judge, and get a recommended winner. A/B testing for RAG.",
  },
];

const failureTypes = [
  "Healthy answer",
  "Correct refusal",
  "Retrieval miss",
  "Unsupported claim",
  "Wrong answer",
  "Needs review",
];

export default function Home() {
  return (
    <main className="min-h-screen bg-[#050505] text-zinc-100">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <section className="mx-auto flex min-h-screen max-w-6xl flex-col justify-center px-6 py-20">
        <div className="max-w-4xl">
          <p className="text-sm font-medium uppercase tracking-[0.22em] text-cyan-300">
            TraceroAI
          </p>

          <h1 className="mt-6 text-5xl font-semibold leading-tight md:text-7xl">
            Debug RAG failures before they reach users.
          </h1>

          <p className="mt-6 max-w-3xl text-xl leading-8 text-zinc-300">
            TraceroAI traces, evaluates, and diagnoses why retrieval-augmented
            generation systems produce bad answers — and a recovery agent that
            retries the stage that failed.
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/dashboard"
              className="rounded-md bg-cyan-300 px-5 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-200"
            >
              Open Dashboard
            </Link>
            <Link
              href="/docs"
              className="rounded-md border border-zinc-700 px-5 py-3 text-sm font-semibold text-zinc-100 transition hover:border-zinc-500"
            >
              Docs &amp; Examples
            </Link>
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
            <p className="text-sm text-zinc-500">Evaluation</p>
            <p className="mt-2 text-lg font-medium">Embedding + LLM-judge</p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/70 p-5">
            <p className="text-sm text-zinc-500">Recovery</p>
            <p className="mt-2 text-lg font-medium">LangGraph self-healing</p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/70 p-5">
            <p className="text-sm text-zinc-500">SDK</p>
            <p className="mt-2 text-lg font-medium">
              <code className="text-cyan-300">pip install traceroai</code>
            </p>
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

client = TraceroClient(
    base_url="https://traceroai.onrender.com",
    api_key="your_project_key",
)

with client.trace(user_question) as t:
    t.log_retrieval(retrieved_chunks, strategy="hybrid")
    t.log_generation(answer, model="gpt-4o-mini")
# auto-times the block and sends the trace on exit`}</code>
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
            See it
          </p>
          <h2 className="mt-4 max-w-3xl text-3xl font-semibold md:text-4xl">
            Every answer becomes a debuggable trace.
          </h2>
          <p className="mt-5 max-w-3xl leading-8 text-zinc-300">
            A wrong answer is a symptom. The trace view shows the per-stage
            evaluation — retrieval, grounding, relevance — that explains the cause.
          </p>

          <div className="mt-10 grid gap-5 lg:grid-cols-2">
            <figure className="overflow-hidden rounded-lg border border-zinc-800 bg-zinc-900/70">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/trace-detail.png"
                alt="TraceroAI trace detail showing the diagnosis and per-stage evaluation"
                className="w-full"
              />
              <figcaption className="border-t border-zinc-800 px-4 py-3 text-sm text-zinc-400">
                Trace detail — answer, diagnosis, and per-evaluator scores.
              </figcaption>
            </figure>
            <figure className="overflow-hidden rounded-lg border border-zinc-800 bg-zinc-900/70">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/dashboard.png"
                alt="TraceroAI reliability dashboard with metrics and failure mix"
                className="w-full"
              />
              <figcaption className="border-t border-zinc-800 px-4 py-3 text-sm text-zinc-400">
                Reliability dashboard — healthy rate, latency, failure mix, experiments.
              </figcaption>
            </figure>
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