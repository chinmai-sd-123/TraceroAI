import Link from "next/link";
import type { ReactNode } from "react";

import { CopyButton } from "@/components/copy-button";
import { CodeTabs, type CodeTab } from "@/components/site/code-tabs";
import { ContentsRail, type ContentsItem } from "@/components/site/contents-rail";
import { Anatomy } from "@/components/site/anatomy";
import { AccuracyTable, TierTable } from "@/components/site/evidence";
import { HeroTitle, Spotlight } from "@/components/site/hero-effects";
import { ArchitectureDiagram, Figure } from "@/components/site/figures";
import { PipelineExplorer } from "@/components/site/pipeline";
import { InvestigationReplay, type ReplayCase } from "@/components/site/replay";
import { TraceRecord } from "@/components/site/trace-record";
import { TraceStream } from "@/components/site/trace-stream";
import { GITHUB_URL, SiteFooter, SiteHeader, repoFile } from "@/components/site/site-chrome";

// The home page reads as a short technical report on TraceroAI: summary,
// findings, method, measured accuracy, and how to run it yourself. Figures are
// screenshots of the real dashboard, taken from the example app in
// examples/recovery-agent.

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "TraceroAI",
  applicationCategory: "DeveloperApplication",
  operatingSystem: "Any",
  description:
    "Open-source tracing and evaluation for RAG pipelines. TraceroAI checks retrieval, grounding and the answer for every response and names the stage that failed.",
  url: "https://www.traceroai.tech",
  license: "https://www.apache.org/licenses/LICENSE-2.0",
  offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
};

const CONTENTS: ContentsItem[] = [
  { id: "summary", label: "Summary" },
  { id: "finds", label: "What it finds" },
  { id: "decides", label: "How it decides" },
  { id: "recovery", label: "Self-healing recovery" },
  { id: "experiments", label: "Experiments" },
  { id: "accuracy", label: "Measured accuracy" },
  { id: "architecture", label: "Architecture" },
  { id: "run", label: "Run it yourself" },
];

// Real traces from the example app (examples/recovery-agent), as the LLM judge
// diagnosed them. Each note is the judge's reason, shortened.
const REPLAY: ReplayCase[] = [
  {
    tab: "Unsupported claim",
    traceId: "5f7bf901",
    model: "gpt-4o-mini",
    latency: "1.68 s",
    question: "is money within 10 days refunded?",
    answer:
      "Yes, money is typically refunded within 10 days, as refunds are processed within 5 to 7 business days after approval, which usually occurs within 1 business day of submission.",
    unsupported: "money is typically refunded within 10 days",
    stages: [
      { name: "Retrieval", state: "pass", note: "The context covers the 5 to 7 day refund window." },
      { name: "Grounding", state: "fail", cause: true, note: "1 of 4 claims isn't supported: the context never says 10 days." },
      { name: "Answer", state: "pass", note: "It addresses the question that was asked." },
    ],
    estimate: "Preliminary · term overlap: unclear",
    verdict: { label: "Unsupported claim", tone: "cause", reason: "The answer says something the retrieved context doesn't." },
    recovery: [
      { label: "Unsupported", healthy: false },
      { label: "Unsupported", healthy: false, action: "stricter prompt" },
      { label: "Healthy", healthy: true, action: "stricter prompt" },
    ],
  },
  {
    tab: "Wrong answer",
    traceId: "f82d0284",
    model: "gpt-4o-mini",
    latency: "999 ms",
    question: "What is your adress and refund policy?",
    answer: "I don't know.",
    stages: [
      { name: "Retrieval", state: "pass", note: "The context holds the refund policy, though no address." },
      { name: "Grounding", state: "review", note: "No factual claims to check in a refusal." },
      { name: "Answer", state: "fail", cause: true, note: "It refused, but the refund half was answerable." },
    ],
    estimate: "Preliminary · term overlap: failed",
    verdict: { label: "Wrong answer", tone: "cause", reason: "The model refused, but the retrieved context was relevant." },
  },
  {
    tab: "Healthy",
    traceId: "b59e4ce1",
    model: "gpt-4o-mini",
    latency: "1.61 s",
    question: "How long does a refund take?",
    answer:
      "A refund typically takes 5 to 7 business days to process after the request is approved. The approval review usually completes within 1 business day of submission.",
    stages: [
      { name: "Retrieval", state: "pass", note: "The context states the processing time." },
      { name: "Grounding", state: "pass", note: "All 3 claims are supported by the context." },
      { name: "Answer", state: "pass", note: "A specific timeframe, as asked." },
    ],
    estimate: "Preliminary · term overlap: passed",
    verdict: { label: "Healthy answer", tone: "pass", reason: "Retrieval, grounding and answer checks all passed." },
  },
];

const SEND_TABS: CodeTab[] = [
  {
    label: "Context manager",
    code: `from traceroai import TraceroClient

client = TraceroClient(base_url="http://localhost:8000")

with client.trace(question) as t:
    chunks = retrieve(question, top_k=3)
    t.log_retrieval(chunks, strategy="vector")
    prompt = build_prompt(question, chunks)
    t.log_prompt(prompt, version="grounded_v1")
    answer = llm(prompt)
    t.log_generation(answer, model="gpt-4o-mini")
# Each step is timed, and the trace is sent in the background.`,
  },
  {
    label: "Decorator",
    code: `from traceroai import TraceroClient

client = TraceroClient(base_url="http://localhost:8000")

@client.traced(model="gpt-4o-mini", strategy="vector")
def answer(question: str):
    chunks = retrieve(question, top_k=3)
    return generate(question, chunks), chunks   # (answer, chunks)`,
  },
];

const RECOVERY_CODE: CodeTab[] = [
  {
    label: "RecoveryAgent",
    code: `from traceroai.recovery import RecoveryAgent

agent = RecoveryAgent(
    client,
    retrieve=retrieve,    # (question, top_k) -> chunks
    generate=generate,    # (question, context) -> answer
    max_attempts=3,
)
result = agent.run("Is money refunded within 10 days?")
result["succeeded"], result["attempts"], result["trace_ids"]`,
  },
];

const EXPERIMENT_CODE: CodeTab[] = [
  {
    label: "run_experiment",
    code: `from traceroai.eval import Case, Variant, run_experiment

result = run_experiment(
    client=client,
    dataset=[Case("refunds", "How long does a refund take?", "5 to 7 business days")],
    retrieve=retrieve,
    generate=generate,
    variants=[Variant("k2", "top_k=2", top_k=2), Variant("k5", "top_k=5", top_k=5)],
)
print(result.recommendation)`,
  },
];

const SELF_HOST: CodeTab[] = [
  {
    label: "Terminal",
    language: "bash",
    code: `git clone ${GITHUB_URL}.git
cd TraceroAI
docker compose -f infra/docker-compose.yml up --build
# API on http://localhost:8000, dashboard on http://localhost:3000`,
  },
];

export default function Home() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <a
        href="#summary"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-30 focus:rounded focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <SiteHeader current="home" />

      <Spotlight className="relative">
      <TraceRecord className="trace-record-lit z-[1]" />
      <section id="summary" aria-labelledby="title" className="relative scroll-mt-20 overflow-hidden border-b border-line">
        <TraceRecord />
        <div className="relative mx-auto max-w-[84rem] px-4 pt-8 pb-6 sm:px-8 lg:pt-12">
          <div className="crop-marks grid items-center gap-10 py-8 sm:px-8 xl:grid-cols-[minmax(0,1fr)_minmax(0,37rem)] xl:gap-14 xl:py-12">
            <span className="crop tl max-sm:hidden" aria-hidden="true" />
            <span className="crop tr max-sm:hidden" aria-hidden="true" />
            <span className="crop bl max-sm:hidden" aria-hidden="true" />
            <span className="crop br max-sm:hidden" aria-hidden="true" />
            <div className="min-w-0">
              <HeroTitle />
              <p className="mt-6 max-w-[48ch] text-lg leading-8 text-ink-muted">
                TraceroAI records every answer your pipeline gives, checks retrieval, grounding and the answer itself,
                and names the stage that broke. Each verdict says whether an LLM judge or a cheap estimate made it.
              </p>
              <div className="mt-8 flex flex-wrap items-center gap-3">
                <div className="flex max-w-full items-center gap-3 rounded border border-line-strong bg-surface py-1.5 pr-1.5 pl-3.5">
                  <code className="font-dash-mono text-sm whitespace-nowrap">
                    <span className="text-ink-faint select-none">$ </span>pip install traceroai
                  </code>
                  <CopyButton text="pip install traceroai" />
                </div>
                <Link href="/docs/quickstart" className="rounded bg-accent px-4 py-2.5 text-sm font-medium text-white hover:bg-accent/90">
                  Read the quickstart
                </Link>
                <a href={GITHUB_URL} className="rounded border border-line-strong bg-surface px-4 py-2.5 text-sm font-medium hover:bg-sunken">
                  View on GitHub
                </a>
              </div>
              <dl className="mt-10 grid max-w-xl grid-cols-3 gap-px overflow-hidden rounded border border-line bg-line text-sm">
                <div className="bg-surface px-3 py-3 sm:px-4">
                  <dt className="text-xs text-ink-muted">Judge accuracy</dt>
                  <dd className="mt-0.5 font-semibold">
                    <a href="#accuracy" className="hover:underline">94–96%</a>
                  </dd>
                </div>
                <div className="bg-surface px-3 py-3 sm:px-4">
                  <dt className="text-xs text-ink-muted">Licence</dt>
                  <dd className="mt-0.5 font-semibold">Open source, Apache-2.0</dd>
                </div>
                <div className="bg-surface px-3 py-3 sm:px-4">
                  <dt className="text-xs text-ink-muted">Runs on</dt>
                  <dd className="mt-0.5 font-semibold">Your servers</dd>
                </div>
              </dl>
            </div>
            <div className="min-w-0">
              <InvestigationReplay cases={REPLAY} />
            </div>
          </div>
        </div>
        <div className="relative pb-6">
          <TraceStream />
          <p className="mx-auto mt-3 max-w-[84rem] px-4 text-xs text-ink-muted sm:px-8">
            Each mark is one answer, checked at retrieval, grounding and the answer: red where it broke, amber where the
            checks couldn&apos;t decide, hatched where only an estimate has looked.
          </p>
        </div>
      </section>
      </Spotlight>

      <Anatomy />

      <div className="mx-auto max-w-[84rem] border-t border-line px-4 sm:px-8 lg:grid lg:grid-cols-[12.5rem_minmax(0,1fr)] lg:gap-12">
        <aside className="hidden lg:block">
          <div className="sticky top-24 pt-14">
            <ContentsRail items={CONTENTS} />
          </div>
        </aside>

        <main className="min-w-0">
          <Section id="finds" title="Three stages, one probable cause">
            <Prose>
              A RAG answer can go wrong in three places: the retriever fetched the wrong documents, the model said
              something the documents don&apos;t support, or it answered a different question. TraceroAI checks all
              three for every trace and names the first that failed, so a bad answer becomes a lookup rather than a
              guess.
            </Prose>
            <div className="mt-8">
              <PipelineExplorer />
            </div>
            <div className="mt-12">
              <Figure
                n={1}
                src="/product/fig-execution.png"
                alt="The execution timeline of a trace: query, retrieval in 223 milliseconds, prompt, generation in 1.45 seconds and evaluation, with the generation step open showing the grounding check failed and the answer check passed."
                width={872}
                height={495}
                sizes="(min-width: 1024px) 60rem, 100vw"
              >
                In the dashboard: every step of a trace, timed, with what went in, what came out, and the check that
                judged it. Hover to look closer.
              </Figure>
            </div>
          </Section>

          <Section id="decides" title="Every verdict says who made it">
            <Prose>
              Checks run in three tiers. The cheap ones run immediately; the LLM judge runs in the background when you
              give the server a provider key. The dashboard draws a judge&apos;s verdict solid and calls it Final, and
              draws an estimate hatched and calls it Preliminary, so you always know how much to trust what you&apos;re
              reading.
            </Prose>
            <div className="mt-8">
              <TierTable />
            </div>
            <p className="mt-3 max-w-[70ch] text-sm text-ink-muted">
              Without a judge configured, every diagnosis is Preliminary and the dashboard says so. When the judge
              disagrees with an estimate, the estimate stays visible, struck through.
            </p>
          </Section>

          <Section id="recovery" title="When a stage fails, retry that stage">
            <Prose>
              The optional RecoveryAgent wraps your own retrieve and generate functions. After a retrieval miss it
              retrieves more; after an unsupported claim it regenerates with a stricter prompt. Every attempt is traced
              and grouped into one run, so you can see what failed, what the agent changed, and how it ended. By
              default it only retries on the judge&apos;s verdicts, not on estimates.
            </Prose>
            <div className="mt-8 grid items-start gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
              <Figure
                n={2}
                src="/product/fig-recovery.png"
                alt="A recovery run in the dashboard: the original attempt and a retry were unsupported claims, the agent regenerated with a stricter prompt each time, and the third attempt was healthy."
                width={844}
                height={328}
                sizes="(min-width: 1280px) 36rem, 100vw"
              >
                One run, attempt by attempt, with the agent&apos;s decision between them.
              </Figure>
              <CodeTabs tabs={RECOVERY_CODE} caption="pip install &quot;traceroai[recovery]&quot;" />
            </div>
          </Section>

          <Section id="experiments" title="Show that a change helps before it ships">
            <Prose>
              Run the same labelled questions through each version of your pipeline, a different top_k, prompt or
              model, and let the judge grade every answer. The dashboard shows each variant&apos;s score and the
              questions where they disagree, which is where the change actually made a difference.
            </Prose>
            <div className="mt-8 grid items-start gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
              <Figure
                n={3}
                src="/product/fig-experiment.png"
                alt="An experiment's question grid: ten questions graded for top_k 2, 3 and 5. The variants disagree on one question, which top_k 3 got wrong."
                width={814}
                height={681}
                sizes="(min-width: 1280px) 36rem, 100vw"
              >
                Ten questions, three variants: they disagree on one, and it&apos;s listed first.
              </Figure>
              <CodeTabs tabs={EXPERIMENT_CODE} />
            </div>
          </Section>

          <Section id="accuracy" title="How often the diagnosis is right">
            <Prose>
              We measured each tier against 117 labelled traces. The numbers below are the whole result, not a
              selection; the{" "}
              <a href={repoFile("docs/evaluation-benchmark.md")} className="text-accent underline">
                full report
              </a>{" "}
              lists every verdict and how to reproduce it.
            </Prose>
            <div className="mt-8">
              <AccuracyTable />
            </div>
            <p className="mt-3 max-w-[70ch] text-sm text-ink-muted">
              The cases come from one small support-style knowledge base, and most of their labels follow from how they
              were constructed. Treat the figures as a comparison between tiers, not as accuracy on your production
              traffic.
            </p>
          </Section>

          <Section id="architecture" title="What runs where">
            <Prose>
              Everything runs on your machine or your servers: one Docker Compose file starts the API, the queue, the
              worker and the dashboard. Trace data leaves only if you configure an LLM provider for the judge, and then
              only to that provider.
            </Prose>
            <div className="mt-8">
              <ArchitectureDiagram />
            </div>
          </Section>

          <Section id="run" title="Run it yourself">
            <Prose>Start the stack, point the SDK at it, and send your first trace.</Prose>
            <div className="mt-8 grid items-start gap-6 xl:grid-cols-2">
              <div className="min-w-0">
                <h3 className="mb-2 text-sm font-semibold">1. Start TraceroAI</h3>
                <CodeTabs tabs={SELF_HOST} />
                <p className="mt-3 text-sm text-ink-muted">
                  Add <code className="font-dash-mono text-[0.8125rem] text-ink">TRACEROAI_OPENAI_API_KEY</code> to the
                  environment to turn on the LLM judge.
                </p>
              </div>
              <div className="min-w-0">
                <h3 className="mb-2 text-sm font-semibold">2. Send a trace from your pipeline</h3>
                <CodeTabs tabs={SEND_TABS} caption="Ways to send a trace" />
              </div>
            </div>
            <p className="mt-8 text-sm">
              <Link href="/docs" className="font-medium text-accent hover:underline">
                Read the documentation
              </Link>{" "}
              <span className="text-ink-muted">for the full SDK reference, recovery options and API keys.</span>
            </p>
          </Section>
        </main>
      </div>

      <SiteFooter />
    </>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="scroll-mt-20 border-t border-line pt-12 pb-16 first:border-t-0">
      <h2 id={`${id}-title`} className="heading-wipe text-[1.75rem] leading-tight font-bold tracking-[-0.02em] text-balance">
        {title}
      </h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Prose({ children }: { children: ReactNode }) {
  return <p className="max-w-[68ch] text-base leading-7 text-ink-muted">{children}</p>;
}
