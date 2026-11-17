import Link from "next/link";
import type { ReactNode } from "react";

import { CopyButton } from "@/components/copy-button";
import { BenchmarkStream } from "@/components/site/benchmark-stream";
import { IntegrationMatrix, RoutesDiagram, Taxonomy } from "@/components/site/capabilities";
import { CaseFile } from "@/components/site/case-file";
import { CodeTabs, type CodeTab } from "@/components/site/code-tabs";
import { AccuracyTable, PerLabelTable, TierTable } from "@/components/site/evidence";
import { ArchitectureDiagram, Figure } from "@/components/site/figures";
import { HeroTitle, Spotlight } from "@/components/site/hero-effects";
import { IssueList } from "@/components/site/issue-list";
import { LightTable } from "@/components/site/light-table";
import { RecoveryRun } from "@/components/site/recovery-run";
import { RedThread } from "@/components/site/red-thread";
import { GITHUB_URL, SiteFooter, SiteHeader, repoFile } from "@/components/site/site-chrome";
import { Terminal } from "@/components/site/terminal";
import { TraceRecord } from "@/components/site/trace-record";
import { TreeToVerdict } from "@/components/site/tree-to-verdict";

// The home page follows one real failed run from the example app (trace
// 5f7bf901) from top to bottom: the case opens in the hero, the trace folds
// into a verdict, the run is taken apart on the light table, and a red thread
// ties it all together down to the recovery run that fixed it. Everything
// shown is real data or a real screenshot; planned features say "Planned".

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "TraceroAI",
  applicationCategory: "DeveloperApplication",
  operatingSystem: "Any",
  description:
    "Open-source failure diagnosis for RAG pipelines. TraceroAI checks every answer, names the step that failed, shows the evidence, and says whether an LLM judge or an estimate decided.",
  url: "https://www.traceroai.tech",
  license: "https://www.apache.org/licenses/LICENSE-2.0",
  offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
};

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
result["succeeded"], result["trace_ids"]`,
  },
];

const EXPERIMENT_CODE: CodeTab[] = [
  {
    label: "run_experiment",
    code: `from traceroai.eval import Case, Variant, run_experiment

result = run_experiment(
    client=client,
    dataset=[
        Case("refunds", "How long does a refund take?",
             "5 to 7 business days"),
    ],
    retrieve=retrieve,
    generate=generate,
    variants=[
        Variant("k2", "top_k=2", top_k=2),
        Variant("k5", "top_k=5", top_k=5),
    ],
)
print(result.recommendation)`,
  },
];

export default function Home() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-30 focus:rounded focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <SiteHeader current="home" />

      <main id="main" className="relative overflow-x-clip">
        <RedThread />

        {/* 1. The case opens */}
        <Spotlight className="relative">
          <TraceRecord className="trace-record-lit z-[1]" />
          <section aria-labelledby="title" data-thread="turn" className="relative z-[2] overflow-hidden">
            <TraceRecord />
            <div data-thread="gutter" className="relative mx-auto max-w-[84rem] px-4 pt-6 pb-10 sm:px-8 lg:pt-10 lg:pb-16">
              <div className="crop-marks grid items-center gap-12 py-8 sm:px-10 xl:grid-cols-[minmax(0,1fr)_minmax(0,34rem)] xl:gap-16 xl:py-12">
                <span className="crop tl max-sm:hidden" aria-hidden="true" />
                <span className="crop tr max-sm:hidden" aria-hidden="true" />
                <span className="crop bl max-sm:hidden" aria-hidden="true" />
                <span className="crop br max-sm:hidden" aria-hidden="true" />
                <div className="min-w-0">
                  <HeroTitle />
                  <p className="mt-7 max-w-[44ch] text-[19px] leading-8 text-ink-muted">
                    TraceroAI reads every run of your RAG pipeline, names the step that failed, and shows the evidence,
                    including whether a judge or an estimate decided.
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
                  </div>
                  <p className="mt-4 text-sm">
                    <a href="#decides" className="font-medium text-accent underline-offset-4 hover:underline">
                      See how it decides
                    </a>
                  </p>
                  <ul className="mt-12 grid max-w-xl grid-cols-3 gap-4 sm:gap-6">
                    <Proof value="94–96%" href="#accuracy">
                      of diagnoses right when the judge decides
                    </Proof>
                    <Proof value="Apache-2.0" href={repoFile("LICENSE")}>
                      open source, no hosted service
                    </Proof>
                    <Proof value="1 command" href="#run">
                      starts it on your own servers
                    </Proof>
                  </ul>
                </div>
                <div className="min-w-0">
                  <CaseFile />
                </div>
              </div>
            </div>
          </section>
        </Spotlight>

        {/* The benchmark, moving: the 117 cases behind the accuracy figures. */}
        <BenchmarkStream />

        {/* 2. A trace isn't an answer */}
        <TreeToVerdict />

        {/* 3. The light table */}
        <LightTable />

        <div className="mx-auto max-w-[84rem] px-4 sm:px-8">
          <div>
            {/* 4. How it decides, and how sure */}
            <Section id="decides" title="Every verdict says who made it">
              <Prose>
                Checks run in three tiers. The cheap ones run at once; the LLM judge runs in the background when you give the
                server a provider key. A judge&apos;s verdict is drawn solid and called Final. An estimate is drawn hatched and
                called Preliminary.
              </Prose>
              <div className="focus-in mt-8">
                <TierTable />
              </div>
              <p className="mt-3 max-w-[70ch] text-sm text-ink-muted">
                Without a judge configured, every diagnosis is Preliminary and the dashboard says so. When the judge disagrees
                with an estimate, the estimate stays visible, struck through.
              </p>

              <h3 id="accuracy" className="focus-in mt-14 scroll-mt-20 text-xl font-semibold tracking-[-0.015em]">
                How often it&apos;s right
              </h3>
              <p className="mt-3 max-w-[68ch] text-base leading-7 text-ink-muted">
                We measured each tier against 117 labelled traces. These are the whole result, not a selection.
                <sup className="ml-0.5 text-[0.7em]">
                  <a href="#fn-1" id="fn-1-ref" className="text-accent">1</a>
                </sup>
              </p>
              <div className="mt-6">
                <AccuracyTable />
                <PerLabelTable />
              </div>
              <p className="mt-3 max-w-[70ch] text-sm text-ink-muted">
                The cases come from one small support-style knowledge base. Treat the figures as a comparison between tiers, not
                as accuracy on your traffic.
              </p>
              <p id="fn-1" className="mt-6 border-t border-line pt-3 text-xs text-ink-muted">
                <span className="mr-1 text-accent">1</span>
                Full report, with every verdict and how to reproduce it:{" "}
                <a href={repoFile("docs/evaluation-benchmark.md")} className="text-accent underline">
                  docs/evaluation-benchmark.md
                </a>
                . <a href="#fn-1-ref" className="text-accent" aria-label="Back to the text">↩</a>
              </p>
            </Section>

            {/* 5. What it can diagnose */}
            <Section id="diagnose" title="What it can diagnose">
              <Prose>
                Today TraceroAI diagnoses RAG pipelines: it checks three stages and names the first that failed. Agent runs come
                next, and they&apos;re marked as planned until they ship with measured accuracy.
              </Prose>
              <div className="focus-in mt-8">
                <Taxonomy />
              </div>
            </Section>

            {/* 6. From one failure to a fix */}
            <Section id="fix" title="From one failure to a fix you can prove" thread>
              <ol className="space-y-16">
                <Step n={1} title="Failures group into issues">
                  <Prose>
                    Five hundred failed runs are usually a dozen causes. Failures with the same cause become one issue, with a
                    count, first and last seen, and a state: open, resolved, or regressed if it comes back.
                  </Prose>
                  <div className="mt-6 max-w-[52rem]">
                    <IssueList />
                  </div>
                </Step>

                <Step n={2} title="Retry the step that failed">
                  <Prose>
                    The optional RecoveryAgent wraps your own retrieve and generate functions. After a retrieval miss it retrieves
                    more; after an unsupported claim it regenerates with a stricter prompt. Every attempt is traced. By default it
                    only retries on the judge&apos;s verdicts.
                  </Prose>
                  <div className="meet mt-6 grid items-start gap-6 xl:grid-cols-2">
                    <div data-thread="end">
                      <RecoveryRun />
                    </div>
                    <CodeTabs tabs={RECOVERY_CODE} caption="pip install &quot;traceroai[recovery]&quot;" />
                  </div>
                </Step>

                <Step n={3} title="Show the change helps before it ships">
                  <Prose>
                    Run the same labelled questions through each version of your pipeline and let the judge grade every answer.
                    You get each variant&apos;s score, tokens and cost, and the questions where they disagree.
                  </Prose>
                  <div className="meet mt-6 grid items-start gap-6 xl:grid-cols-2">
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
                </Step>
              </ol>
            </Section>

            {/* 7. Works with what you run */}
            <Section id="works-with" title="Works with what you run">
              <Prose>
                Send traces from Python, over HTTP, or from any app already instrumented with OpenTelemetry. Routes still
                planned are marked that way until they ship.
              </Prose>
              <div className="focus-in mt-10 hidden rounded-md border border-line bg-sunken/50 px-6 py-6 md:block">
                <RoutesDiagram />
              </div>
              <div className="meet mt-8 grid items-start gap-6 xl:grid-cols-2">
                <IntegrationMatrix />
                <CodeTabs tabs={SEND_TABS} caption="Two ways to send a trace" />
              </div>
            </Section>

            {/* 8. What runs where */}
            <Section id="architecture" title="What runs where">
              <Prose>
                Everything runs on your machine or your servers. Postgres is the only thing it has to have; Redis and a separate
                worker are there for more traffic. Trace data leaves only if you configure an LLM provider for the judge, and then
                only to that provider.
              </Prose>
              <div className="focus-in mt-8">
                <ArchitectureDiagram />
              </div>
            </Section>

            {/* 9. Run it yourself */}
          </div>
        </div>

        {/* 9. Run it yourself: the closing band. */}
        <section id="run" aria-labelledby="run-title" className="closing-band scroll-mt-14 border-t border-line">
          <div className="mx-auto grid max-w-[84rem] items-center gap-12 px-4 py-24 sm:px-8 xl:grid-cols-[minmax(0,1fr)_minmax(0,40rem)] xl:gap-16">
            <div>
              <h2 id="run-title" className="focus-in text-[clamp(2.25rem,4.6vw,3.5rem)] leading-[1.02] font-bold tracking-[-0.035em] text-balance">
                Find the step that broke, on your own servers.
              </h2>
              <p className="focus-in mt-5 max-w-[46ch] text-[17px] leading-8 text-ink-muted">
                One command starts the API, the worker, Postgres and the dashboard. Add the demo profile and the dashboard opens
                with 30 recorded runs already in it.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link href="/docs/quickstart" className="rounded bg-accent px-4 py-2.5 text-sm font-medium text-white hover:bg-accent/90">
                  Read the quickstart
                </Link>
                <a href={GITHUB_URL} className="rounded border border-line-strong bg-surface px-4 py-2.5 text-sm font-medium hover:bg-sunken">
                  View on GitHub
                </a>
              </div>
            </div>
            <div className="focus-in min-w-0">
              <Terminal />
              <p className="mt-3 text-sm text-ink-muted">
                Add <code className="font-dash-mono text-[0.8125rem] text-ink">TRACEROAI_OPENAI_API_KEY</code> to turn on the LLM
                judge.
              </p>
              <dl className="mt-8 grid border-y border-line-strong/70 text-sm sm:grid-cols-3">
                <Fact term="Licence">Apache-2.0</Fact>
                <Fact term="Hosting">Yours. No hosted service.</Fact>
                <Fact term="Telemetry">None. Your copy sends nothing.</Fact>
              </dl>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter flush />
    </>
  );
}

function Section({ id, title, children, thread = false }: { id: string; title: string; children: ReactNode; thread?: boolean }) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-title`}
      data-thread={thread ? "pin" : undefined}
      className="scroll-mt-20 border-t border-line pt-16 pb-20 first:border-t-0"
    >
      <h2 id={`${id}-title`} className="focus-in text-[2.5rem] leading-[1.05] font-bold tracking-[-0.03em] text-balance">
        {title}
      </h2>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <li className="relative grid gap-x-6 sm:grid-cols-[2.5rem_minmax(0,1fr)]">
      <span className="font-dash-mono text-sm text-ink-faint sm:pt-[0.3rem]">{String(n).padStart(2, "0")}</span>
      {/* The rule from this step's number down to the next one's. */}
      {n < 3 && (
        <span className="step-rail absolute top-8 -bottom-12 left-[0.55rem] hidden w-px bg-line-strong sm:block" aria-hidden="true" />
      )}
      <div className="min-w-0">
        <h3 className="focus-in text-xl font-semibold tracking-[-0.015em]">{title}</h3>
        <div className="mt-3">{children}</div>
      </div>
    </li>
  );
}

/** A hero proof point: a figure set large, what it means, and a link to the evidence. */
function Proof({ value, href, children }: { value: string; href: string; children: ReactNode }) {
  return (
    <li className="border-t-2 border-ink pt-3">
      <a href={href} className="group block">
        <span className="block text-[clamp(1.25rem,2.4vw,1.625rem)] leading-none font-bold tracking-[-0.02em] whitespace-nowrap tabular-nums group-hover:text-accent">
          {value}
        </span>
        <span className="mt-2 block text-[13px] leading-5 text-ink-muted">{children}</span>
      </a>
    </li>
  );
}

function Fact({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="py-3 pr-4 [&:not(:first-child)]:border-l [&:not(:first-child)]:border-line [&:not(:first-child)]:pl-4">
      <dt className="text-xs text-ink-muted">{term}</dt>
      <dd className="mt-0.5 font-semibold">{children}</dd>
    </div>
  );
}

function Prose({ children }: { children: ReactNode }) {
  return <p className="focus-in max-w-[68ch] text-[17px] leading-8 text-ink-muted">{children}</p>;
}
