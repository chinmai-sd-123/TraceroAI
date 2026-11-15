import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { CopyButton } from "@/components/copy-button";
import { CodeTabs, type CodeTab } from "@/components/site/code-tabs";
import { ContentsRail, type ContentsItem } from "@/components/site/contents-rail";
import { SiteFooter, SiteHeader, repoFile } from "@/components/site/site-chrome";
import { publicApiConfigured } from "@/lib/site-mode";

import { DIAGNOSIS_NAMES, causeStage, diagnosisTone } from "../dashboard/ui";
import { Playground } from "./playground";

export const metadata: Metadata = {
  title: "Documentation",
  description:
    "Install the TraceroAI SDK, run the stack with Docker Compose, send traces from any RAG pipeline, and add self-healing recovery and experiments.",
};

const CONTENTS: ContentsItem[] = [
  { id: "install", label: "Install" },
  { id: "self-host", label: "Run the stack" },
  { id: "trace", label: "Send traces" },
  { id: "reference", label: "SDK reference" },
  { id: "diagnosis", label: "Diagnoses" },
  { id: "recovery", label: "Self-healing recovery" },
  { id: "experiments", label: "Experiments" },
  { id: "auth", label: "API keys and projects" },
  { id: "config", label: "Configuration" },
  { id: "http-api", label: "HTTP API" },
  { id: "troubleshooting", label: "Troubleshooting" },
  { id: "try", label: "Try it" },
];

const SELF_HOST: CodeTab[] = [
  {
    label: "Terminal",
    language: "bash",
    code: `git clone https://github.com/chinmai-sd-123/TraceroAI.git
cd TraceroAI
docker compose -f infra/docker-compose.yml up --build`,
  },
];

const TRACE_TABS: CodeTab[] = [
  {
    label: "Context manager",
    code: `from traceroai import TraceroClient

client = TraceroClient(base_url="http://localhost:8000")   # or set TRACEROAI_API_URL

with client.trace("How long does a refund take?") as t:
    chunks = retrieve(question, top_k=3)                    # your retriever
    t.log_retrieval(chunks, strategy="hybrid", config={"top_k": 3})
    t.log_prompt(prompt, version="grounded_v1")             # optional
    answer = generate(prompt)                               # your LLM
    t.log_generation(answer, model="gpt-4o-mini", provider="openai")

print(t.trace_id)   # chosen before sending, so you can log it straight away`,
  },
  {
    label: "Decorator",
    code: `from traceroai import TraceroClient

client = TraceroClient(base_url="http://localhost:8000")

@client.traced(model="gpt-4o-mini", strategy="hybrid")
def answer(question: str):
    chunks = retrieve(question)
    return generate(question, chunks), chunks   # must return (answer, chunks)

answer("What is the maximum upload size?")   # traced automatically
# async def functions work the same way.`,
  },
  {
    label: "Low-level",
    code: `client.log_trace(
    query={"original": question},
    retrieval={"strategy": "hybrid", "chunks": chunks},
    generation={"model": "gpt-4o-mini", "answer": answer},
    prompt={"content": prompt},                               # optional
    latency={"total_ms": 1171, "retrieval_ms": 230},          # optional
    project={"project_id": "my-app", "environment": "prod"},  # optional
    metadata={"user_tier": "free"},                           # optional
)
# Evaluations and the diagnosis are computed by the server; you don't send them.`,
  },
];

const RECOVERY_TABS: CodeTab[] = [
  {
    label: "Run the agent",
    code: `from traceroai.recovery import RecoveryAgent

agent = RecoveryAgent(
    client,
    retrieve=my_retrieve,    # (question, top_k) -> list of chunk dicts
    generate=my_generate,    # (question, context) -> answer string
    max_attempts=3,
)

result = agent.run("How long does a refund take?")
result["answer"]       # the final answer
result["diagnosis"]    # its diagnosis
result["attempts"]     # how many tries it took
result["succeeded"]    # whether it reached a healthy answer
result["trace_ids"]    # one trace per attempt, grouped as one run`,
  },
  {
    label: "Load your own documents",
    code: `from langchain_text_splitters import RecursiveCharacterTextSplitter

# TraceroAI doesn't load documents; your retriever does. Load any format, split,
# embed, and return chunks from retrieve(question, top_k).
# examples/recovery-agent in the repository shows the whole flow.
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)
chunks = splitter.split_text(open("policy.md").read())`,
  },
];

const EXPERIMENT_CODE: CodeTab[] = [
  {
    label: "run_experiment",
    code: `from traceroai.eval import Case, Variant, run_experiment

result = run_experiment(
    client=client,
    dataset=[Case("refund", "How long does a refund take?", "5 to 7 business days.")],
    retrieve=my_retrieve,    # (question, top_k) -> list of chunk dicts
    generate=my_generate,    # (question, context) -> answer string
    variants=[Variant("k3", "top_k=3", top_k=3), Variant("k5", "top_k=5", top_k=5)],
    project_id="my-app",
)
print(result.recommendation)
result.cases   # every question's result per variant`,
  },
];

const KEYS_CODE: CodeTab[] = [
  {
    label: "Create and use a key",
    language: "bash",
    code: `# from services/api, or: docker compose exec api python -m app.keys ...
python -m app.keys create --project my-app --name "my-app production"
python -m app.keys create --admin --name "dashboard"
python -m app.keys list
python -m app.keys revoke trk_AbCdEfGh`,
  },
];

const METHODS: Array<{ sig: string; body: string }> = [
  { sig: "TraceroClient(base_url=None, api_key=None, enabled=None)", body: "Defaults to TRACEROAI_API_URL, TRACEROAI_API_KEY and TRACEROAI_ENABLED. Sending happens in the background and never raises into your code." },
  { sig: "client.trace(query, *, rewritten=, project=, metadata=)", body: "Context manager. Times each logged step and sends the trace when the block exits." },
  { sig: "t.log_retrieval(chunks, *, strategy=, config=)", body: "The retrieved chunks: dicts with at least a text field; rank and chunk_id are filled in if missing." },
  { sig: "t.log_prompt(content, *, version=, template_name=)", body: "Optional. The prompt sent to the model." },
  { sig: "t.log_generation(answer, *, model, provider=, temperature=, ...)", body: "The answer. Pass prompt_tokens and completion_tokens and the server works out the cost." },
  { sig: "client.traced(*, model, strategy='vector')", body: "Decorator for a function returning (answer, chunks); sync or async." },
  { sig: "client.log_trace(*, query, retrieval, generation, ...)", body: "Send a whole trace in one call. Returns the trace id." },
  { sig: "client.get_trace(trace_id)", body: "Read a stored trace back, with its evaluations and diagnosis." },
  { sig: "client.flush()", body: "Wait for queued traces to send. Also runs on exit, for up to 2 seconds." },
];

const DIAGNOSES: Array<{ label: keyof typeof DIAGNOSIS_NAMES; meaning: string }> = [
  { label: "healthy_answer", meaning: "Retrieval, grounding and the answer all passed." },
  { label: "correct_refusal", meaning: "The context didn't cover the question, and the model said so." },
  { label: "retrieval_miss", meaning: "The retrieved context doesn't match the question." },
  { label: "low_context_relevance", meaning: "The context is only loosely related to the question." },
  { label: "unsupported_claim", meaning: "The answer states something the context doesn't support." },
  { label: "wrong_answer", meaning: "Grounded, but it doesn't answer the question, or refuses one it could answer." },
  { label: "needs_review", meaning: "The checks couldn't decide; a person should look." },
];

const CONFIG: Array<{ name: string; does: string }> = [
  { name: "TRACEROAI_OPENAI_API_KEY", does: "Turns on embeddings and the LLM judge. Without it every diagnosis is a term-overlap estimate." },
  { name: "TRACEROAI_JUDGE_MODEL", does: "The judge model (default gpt-4o-mini)." },
  { name: "TRACEROAI_JUDGE_BASE_URL", does: "An OpenAI-compatible endpoint for the judge, for other providers or a local model." },
  { name: "TRACEROAI_EMBEDDING_MODEL", does: "The embedding model for the background relevance check." },
  { name: "TRACEROAI_DATABASE_URL", does: "Postgres connection string." },
  { name: "TRACEROAI_REDIS_URL", does: "Redis for the evaluation queue and rate limits. Without it, evaluations run inside the API process." },
  { name: "TRACEROAI_APP_ENV", does: "development (keys optional), staging or production (keys required)." },
  { name: "TRACEROAI_ADMIN_API_KEYS", does: "Keys that can read every project, for example the dashboard's." },
  { name: "TRACEROAI_PUBLIC_READ_PROJECTS", does: "Projects anyone may read without a key, for a public demo." },
  { name: "TRACEROAI_TRACE_RETENTION_DAYS", does: "Delete traces older than this many days." },
  { name: "TRACEROAI_MAX_REQUEST_BYTES", does: "Largest request body accepted (default 1 MB)." },
  { name: "TRACEROAI_PLAYGROUND_ENABLED", does: "Turns on the live playground endpoint used below. Off by default." },
  { name: "TRACEROAI_API_URL / TRACEROAI_API_KEY", does: "Dashboard: where the API is, and the key it reads with (server-side only)." },
  { name: "TRACEROAI_DASHBOARD_PASSWORD", does: "Dashboard: require a shared password to open it." },
];

const TONE = { pass: "bg-pass-soft text-pass", cause: "bg-cause-soft text-cause", warn: "bg-warn-soft text-warn", none: "bg-sunken text-ink-muted" };
const STAGE_NAMES = { retrieval: "Retrieval", grounding: "Grounding", answer: "Answer" };

export default function DocsPage() {
  return (
    <>
      <SiteHeader current="docs" />
      <div className="mx-auto max-w-[84rem] px-4 sm:px-8 lg:grid lg:grid-cols-[12.5rem_minmax(0,1fr)] lg:gap-12">
        <aside className="hidden lg:block">
          <div className="sticky top-24 pt-12">
            <ContentsRail items={CONTENTS} label="On this page" />
          </div>
        </aside>

        <main className="min-w-0 max-w-[52rem] pt-12">
          <h1 className="text-[2.5rem] leading-tight font-bold tracking-[-0.03em]">Documentation</h1>
          <p className="mt-4 max-w-[62ch] text-lg leading-8 text-ink-muted">
            Add the Python SDK to your RAG pipeline and every answer becomes a trace: the question, the retrieved
            chunks, the prompt, the answer and its timing, checked at each stage and given one diagnosis. These
            pages cover running TraceroAI, sending traces, and the optional recovery agent and experiments.
          </p>

          <DocSection id="install" title="Install">
            <div className="flex w-fit max-w-full items-center gap-3 rounded border border-line-strong py-1.5 pr-1.5 pl-3.5">
              <code className="font-dash-mono text-sm">
                <span className="text-ink-faint select-none">$ </span>pip install traceroai
              </code>
              <CopyButton text="pip install traceroai" />
            </div>
            <P>
              The SDK&apos;s only dependency is <Code>httpx</Code>. Sending is best-effort: traces go out in the
              background with retries, and if the API can&apos;t be reached the SDK logs it and carries on. It never
              raises into your application.
            </P>
          </DocSection>

          <DocSection id="self-host" title="Run the stack">
            <P>One command starts Postgres, Redis, the API, the evaluation worker and the dashboard.</P>
            <div className="mt-4">
              <CodeTabs tabs={SELF_HOST} />
            </div>
            <P>
              The API runs on <Code>http://localhost:8000</Code> (interactive API docs at <Code>/docs</Code>) and the
              dashboard on <Code>http://localhost:3000</Code>. Traces get the quick checks out of the box; set{" "}
              <Code>TRACEROAI_OPENAI_API_KEY</Code> before starting to add the LLM judge. The stack starts in
              development mode, where API keys are optional; see{" "}
              <a href="#auth" className="text-accent underline">API keys</a> before exposing it to a network.
            </P>
          </DocSection>

          <DocSection id="trace" title="Send traces">
            <P>
              Three ways in, from most automatic to most explicit. They all produce the same trace. With the context
              manager, log each piece right after the work it records and TraceroAI times every step.
            </P>
            <div className="mt-4">
              <CodeTabs tabs={TRACE_TABS} caption="Ways to send a trace" />
            </div>
          </DocSection>

          <DocSection id="reference" title="SDK reference">
            <P>
              The public surface of <Code>TraceroClient</Code>. From async code, use <Code>aget_trace</Code>,{" "}
              <Code>alog_trace_sync_eval</Code> and <Code>aflush</Code>; sending a trace never blocks, so it needs no
              async version.
            </P>
            <dl className="mt-4 divide-y divide-line rounded border border-line">
              {METHODS.map((m) => (
                <div key={m.sig} className="px-4 py-3">
                  <dt className="font-dash-mono text-[0.8125rem] break-words text-accent">{m.sig}</dt>
                  <dd className="mt-1 text-sm leading-6 text-ink-muted">{m.body}</dd>
                </div>
              ))}
            </dl>
          </DocSection>

          <DocSection id="diagnosis" title="Diagnoses">
            <P>
              Every trace ends with one diagnosis, tied to the stage that failed. The quick check (term overlap) runs
              when the trace arrives; with a provider key, embeddings and the LLM judge follow in the background and
              the judge&apos;s verdict replaces the estimate. The dashboard marks each diagnosis as Final (the judge)
              or Preliminary (an estimate).
            </P>
            <div className="mt-4 overflow-x-auto rounded border border-line">
              <table className="w-full min-w-[34rem] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-line-strong bg-sunken text-left text-xs text-ink-muted">
                    <th scope="col" className="px-4 py-2 font-medium">Diagnosis</th>
                    <th scope="col" className="px-4 py-2 font-medium">Stage</th>
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
            <P>
              How often each tier gets it right is measured on 117 labelled traces; see the{" "}
              <a href={repoFile("docs/evaluation-benchmark.md")} className="text-accent underline">accuracy report</a>.
            </P>
          </DocSection>

          <DocSection id="recovery" title="Self-healing recovery">
            <P>
              An optional LangGraph agent that retries the stage that failed: after a retrieval miss it retrieves more
              context, after an unsupported claim it regenerates with a stricter prompt, up to{" "}
              <Code>max_attempts</Code>. Every attempt is traced and grouped as one run under Recovery runs in the
              dashboard. By default it only retries on the judge&apos;s verdicts, since estimates often flag correct
              answers and each retry costs a generation.
            </P>
            <div className="mt-4 flex w-fit max-w-full items-center gap-3 rounded border border-line-strong py-1.5 pr-1.5 pl-3.5">
              <code className="font-dash-mono text-sm">
                <span className="text-ink-faint select-none">$ </span>pip install &quot;traceroai[recovery]&quot;
              </code>
              <CopyButton text={'pip install "traceroai[recovery]"'} />
            </div>
            <div className="mt-4">
              <CodeTabs tabs={RECOVERY_TABS} caption="Recovery agent" />
            </div>
          </DocSection>

          <DocSection id="experiments" title="Experiments">
            <P>
              Compare versions of your pipeline (top_k, prompt, model) on a labelled dataset. You supply retrieve and
              generate; the harness runs every question through each variant, has the server&apos;s judge grade the
              answers, and recommends a winner. Runs appear under{" "}
              <Link href="/dashboard/eval-runs" className="text-accent underline">Eval runs</Link>, with a grid of
              which variant got which question right. Grading needs the judge configured.
            </P>
            <div className="mt-4">
              <CodeTabs tabs={EXPERIMENT_CODE} />
            </div>
          </DocSection>

          <DocSection id="auth" title="API keys and projects">
            <P>
              A project key stamps every trace, eval run and grading call with its project, and reads back only that
              project. Admin keys read every project; give one to the dashboard. Keys are required in staging and
              production. In development they&apos;re optional, and traces use the <Code>project_id</Code> you
              pass. Keys are stored hashed and managed with a small command-line tool.
            </P>
            <div className="mt-4">
              <CodeTabs tabs={KEYS_CODE} />
            </div>
          </DocSection>

          <DocSection id="config" title="Configuration">
            <P>The settings most deployments touch. All are environment variables.</P>
            <dl className="mt-4 divide-y divide-line rounded border border-line">
              {CONFIG.map((c) => (
                <div key={c.name} className="grid gap-1 px-4 py-3 sm:grid-cols-[18rem_minmax(0,1fr)] sm:gap-4">
                  <dt className="font-dash-mono text-[0.8125rem] break-words">{c.name}</dt>
                  <dd className="text-sm leading-6 text-ink-muted">{c.does}</dd>
                </div>
              ))}
            </dl>
          </DocSection>

          <DocSection id="http-api" title="HTTP API">
            <P>
              The SDK is a thin client over these endpoints, so any language can send traces. Send the key as{" "}
              <Code>Authorization: Bearer &lt;key&gt;</Code>. Your API serves the full schema, with every field, at{" "}
              <Code>/docs</Code> (OpenAPI).
            </P>
            <div className="mt-4 overflow-x-auto rounded border border-line">
              <table className="w-full min-w-[36rem] text-left text-sm">
                <caption className="sr-only">API endpoints</caption>
                <thead className="bg-sunken text-ink-muted">
                  <tr>
                    <th scope="col" className="px-4 py-2 font-medium">
                      Endpoint
                    </th>
                    <th scope="col" className="px-4 py-2 font-medium">
                      What it does
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {ENDPOINTS.map((e) => (
                    <tr key={e.path}>
                      <td className="px-4 py-2.5 align-top font-dash-mono text-[0.8125rem] whitespace-nowrap">
                        {e.path}
                      </td>
                      <td className="px-4 py-2.5 leading-6 text-ink-muted">{e.does}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </DocSection>

          <DocSection id="troubleshooting" title="Troubleshooting">
            <dl className="divide-y divide-line rounded border border-line">
              {TROUBLESHOOTING.map((t) => (
                <div key={t.problem} className="px-4 py-3.5">
                  <dt className="font-semibold">{t.problem}</dt>
                  <dd className="mt-1 max-w-[72ch] text-sm leading-6 text-ink-muted">{t.fix}</dd>
                </div>
              ))}
            </dl>
          </DocSection>

          <DocSection id="try" title="Try it">
            {publicApiConfigured() ? (
              <>
                <P>
                  Ask the demo knowledge base a question. The server retrieves, answers and evaluates it, and shows
                  the trace below. This needs <Code>TRACEROAI_PLAYGROUND_ENABLED</Code> on the API it talks to.
                </P>
                <div className="mt-4">
                  <Playground />
                </div>
              </>
            ) : (
              <P>
                The playground asks your own API a question and shows the trace it produces. Run the stack (see{" "}
                <a href="#self-host" className="text-accent underline">
                  Run the stack
                </a>
                ), set <Code>TRACEROAI_PLAYGROUND_ENABLED=true</Code> on the API, and open this page at{" "}
                <Code>http://localhost:3000/docs#try</Code>.
              </P>
            )}
          </DocSection>
        </main>
      </div>
      <SiteFooter />
    </>
  );
}

const ENDPOINTS: Array<{ path: string; does: string }> = [
  { path: "POST /v1/traces", does: "Send a trace. Returns 202 with the trace id; diagnosis runs in the background." },
  {
    path: "GET /v1/traces",
    does: "List traces. Filters: project_id, diagnosis, model, environment, q, since, until, recovery_run_id; sort=newest, oldest or slowest; limit up to 200, with the next page's cursor in the X-Next-Cursor header.",
  },
  { path: "GET /v1/traces/{id}", does: "One trace with its evaluation, diagnosis and feedback." },
  { path: "DELETE /v1/traces/{id}", does: "Delete a trace. A project key can delete only its own project's." },
  { path: "POST /v1/traces/{id}/feedback", does: "Record a thumbs up or down, with an optional comment." },
  { path: "GET /v1/traces/projects", does: "The projects the key can read." },
  {
    path: "GET /v1/metrics/summary",
    does: "Totals for a project and time range: counts by diagnosis, model and environment, latency and cost.",
  },
  { path: "GET /v1/metrics/timeseries", does: "Traces, healthy traces and p95 latency per hour or day." },
  { path: "GET /v1/recovery-runs", does: "Recovery agent runs, each with its attempts, diagnoses and the lever it pulled." },
  { path: "POST /v1/eval-runs", does: "Upload an eval run or an experiment (what the SDK's run_experiment sends)." },
  { path: "GET /v1/eval-runs/{id}", does: "Read one eval run; GET /v1/eval-runs lists them." },
  { path: "POST /v1/eval/grade", does: "Grade one answer with the LLM judge, without storing a trace." },
  { path: "GET /v1/jobs/stats", does: "The judge queue: waiting, in progress and failed jobs." },
  { path: "GET /health/ready", does: "Readiness: the database is reachable. GET /health is plain liveness." },
  { path: "GET /metrics", does: "Prometheus metrics." },
];

const TROUBLESHOOTING: Array<{ problem: string; fix: ReactNode }> = [
  {
    problem: "The dashboard says it can't reach the API",
    fix: (
      <>
        Check the API is up with <Code>curl http://localhost:8000/health/ready</Code>. The dashboard&apos;s server
        reads <Code>TRACEROAI_API_URL</Code>; in Docker Compose that&apos;s <Code>http://api:8000</Code>, not
        localhost.
      </>
    ),
  },
  {
    problem: "The API rejects requests with 401 or 403",
    fix: (
      <>
        Keys are required in staging and production. Pass <Code>api_key=</Code> to the client or set{" "}
        <Code>TRACEROAI_API_KEY</Code>. A project key reads only its own project; the dashboard needs an admin key.
      </>
    ),
  },
  {
    problem: "Every diagnosis says Preliminary",
    fix: (
      <>
        No judge is configured. Set <Code>TRACEROAI_OPENAI_API_KEY</Code> (or <Code>TRACEROAI_JUDGE_BASE_URL</Code>{" "}
        for another provider) on the API and the worker. New traces are then graded by the judge.
      </>
    ),
  },
  {
    problem: "The sidebar says the judge queue is not connected",
    fix: (
      <>
        <Code>TRACEROAI_REDIS_URL</Code> isn&apos;t set, so the API grades traces in its own process. That&apos;s
        fine for small setups. Add Redis and run <Code>python -m app.worker</Code> when traffic grows.
      </>
    ),
  },
  {
    problem: "Traces are rejected with 413 or 422",
    fix: (
      <>
        413: the request is over <Code>TRACEROAI_MAX_REQUEST_BYTES</Code> (1 MB by default); send fewer or shorter
        chunks, or raise the limit. 422: a field is missing or too long, and the response says which.
      </>
    ),
  },
  {
    problem: "Nothing shows up, and the app shows no error",
    fix: (
      <>
        The SDK never raises into your app; it logs instead. Turn its log on with{" "}
        <Code>logging.getLogger(&quot;traceroai&quot;).setLevel(logging.DEBUG)</Code>, and call{" "}
        <Code>client.flush()</Code> before a short script exits.
      </>
    ),
  },
  {
    problem: "Errors about missing tables or columns after an upgrade",
    fix: (
      <>
        Run the migrations: <Code>python -m app.db.init_db</Code>. Docker Compose does this on every start; on other
        hosts make it the pre-deploy step.
      </>
    ),
  },
  {
    problem: "Docker Compose can't start Postgres or Redis",
    fix: (
      <>
        Another service holds port 5432 or 6379. Stop it, or change the published port in{" "}
        <Code>infra/docker-compose.yml</Code>.
      </>
    ),
  },
];

function DocSection({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="scroll-mt-20 border-t border-line pt-10 pb-12 first-of-type:mt-10">
      <h2 id={`${id}-title`} className="heading-wipe text-[1.5rem] font-bold tracking-[-0.02em]">
        {title}
      </h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function P({ children }: { children: ReactNode }) {
  return <p className="mt-3 max-w-[68ch] leading-7 text-ink-muted first:mt-0">{children}</p>;
}

function Code({ children }: { children: ReactNode }) {
  return <code className="rounded-[3px] bg-sunken px-1 py-px font-dash-mono text-[0.8125rem] text-ink">{children}</code>;
}
