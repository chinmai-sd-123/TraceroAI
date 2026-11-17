// What TraceroAI can diagnose, and what it works with, each marked Available
// or Planned. Nothing planned is presented as available (PRODUCT.md).

export function StatusBadge({ status }: { status: "available" | "planned" }) {
  return status === "available" ? (
    <span className="inline-flex items-center gap-1.5 rounded-[3px] border border-pass/40 bg-pass-soft px-1.5 py-px text-xs font-semibold text-pass">
      <span className="size-1.5 rounded-full bg-pass" aria-hidden="true" />
      Available
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 rounded-[3px] border border-dashed border-ink-faint px-1.5 py-px text-xs font-medium text-ink-muted">
      <span className="size-1.5 rounded-full border border-ink-faint" aria-hidden="true" />
      Planned
    </span>
  );
}

const RAG = [
  { step: "Retrieval", failure: "Retrieval miss", what: "The retrieved context doesn't cover the question." },
  { step: "Grounding", failure: "Unsupported claim", what: "The answer says something the context doesn't." },
  { step: "Answer", failure: "Wrong answer", what: "It answers a different question, or refuses one it could answer." },
];

const ALSO = [
  { label: "Healthy answer", tone: "text-pass", what: "All three checks passed." },
  { label: "Correct refusal", tone: "text-pass", what: "The context didn't have it, and the model said so." },
  { label: "Needs review", tone: "text-warn", what: "The checks couldn't decide; a person should look." },
];

const AGENT = [
  "Wrong tool chosen",
  "Arguments that break the tool's schema",
  "A tool error the agent ignored",
  "The same call repeated",
  "Step limit reached",
];

// Two more real runs from the example app, as the judge diagnosed them.
const MORE = [
  {
    id: "f82d0284",
    question: "What is your adress and refund policy?",
    answer: "I don't know.",
    verdict: "Wrong answer",
    tone: "text-cause",
    why: "It refused, but the context held the refund policy.",
  },
  {
    id: "b59e4ce1",
    question: "How long does a refund take?",
    answer: "A refund typically takes 5 to 7 business days to process after the request is approved…",
    verdict: "Healthy answer",
    tone: "text-pass",
    why: "Retrieval, grounding and answer checks all passed.",
  },
];

export function Taxonomy() {
  return (
    <div className="space-y-5">
      <div className="overflow-hidden rounded-md border border-line-strong">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-sunken px-5 py-3">
          <p className="font-semibold">RAG pipelines</p>
          <StatusBadge status="available" />
        </div>
        <ol className="grid md:grid-cols-3" aria-label="The three stages and the failure each can cause">
          {RAG.map((row, i) => (
            <li key={row.step} className="relative border-line px-5 pt-5 pb-5 max-md:[&:not(:first-child)]:border-t md:[&:not(:first-child)]:border-l">
              <span className="draw-x absolute inset-x-0 top-0 h-[3px] bg-cause" aria-hidden="true" />
              <p className="text-sm text-ink-muted">
                <span className="mr-1.5 font-dash-mono text-ink-faint">{i + 1}</span>
                {row.step}
              </p>
              <p className="mt-2 text-lg font-semibold tracking-[-0.01em] text-cause">{row.failure}</p>
              <p className="mt-1 text-sm leading-6 text-ink-muted">{row.what}</p>
            </li>
          ))}
        </ol>
        <dl className="grid gap-x-8 gap-y-3 border-t border-line px-5 py-4 text-sm sm:grid-cols-3">
          {ALSO.map((item) => (
            <div key={item.label}>
              <dt className={`font-semibold ${item.tone}`}>{item.label}</dt>
              <dd className="text-ink-muted">{item.what}</dd>
            </div>
          ))}
        </dl>
      </div>

      <div className="rounded-md border border-dashed border-line-strong">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-dashed border-line-strong px-5 py-3">
          <p className="font-semibold text-ink-muted">Agent runs</p>
          <StatusBadge status="planned" />
        </div>
        <ul className="rise-rows flex flex-wrap gap-2 px-5 py-4">
          {AGENT.map((item) => (
            <li key={item} className="rounded border border-dashed border-line-strong px-2.5 py-1 text-sm text-ink-muted">
              {item}
            </li>
          ))}
        </ul>
      </div>

      <div className="meet grid gap-4 md:grid-cols-2">
        {MORE.map((run) => (
          <figure key={run.id} className="rounded-md border border-line px-5 py-4">
            <p className="font-dash-mono text-xs text-ink-faint">trace {run.id}</p>
            <p className="mt-1.5 font-semibold">{run.question}</p>
            <p className="mt-1 line-clamp-2 text-sm text-ink-muted">{run.answer}</p>
            <figcaption className="mt-3 border-t border-line pt-3 text-sm">
              <span className={`font-semibold ${run.tone}`}>{run.verdict}.</span>{" "}
              <span className="text-ink-muted">{run.why}</span>
            </figcaption>
          </figure>
        ))}
      </div>
    </div>
  );
}

const ROUTES: Array<{ route: string; how: string; status: "available" | "planned" }> = [
  { route: "Python SDK, sync and async", how: "pip install traceroai", status: "available" },
  { route: "HTTP API, any language", how: "POST /v1/traces", status: "available" },
  { route: "Recovery agent", how: 'pip install "traceroai[recovery]"', status: "available" },
  { route: "OpenTelemetry (OTLP/HTTP)", how: "POST /otlp/v1/traces", status: "available" },
  { route: "LangChain and LangGraph, via OpenInference", how: "LangChainInstrumentor", status: "available" },
  { route: "LlamaIndex", how: "Through OpenInference; not yet tested", status: "planned" },
  { route: "TypeScript SDK", how: "npm", status: "planned" },
];

export function IntegrationMatrix() {
  return (
    <div className="overflow-x-auto rounded-md border border-line-strong">
      <table className="w-full min-w-[30rem] border-collapse text-sm">
        <thead>
          <tr className="border-b border-line-strong bg-sunken text-left text-xs text-ink-muted">
            <th scope="col" className="px-4 py-2 font-medium">Route</th>
            <th scope="col" className="px-4 py-2 font-medium">How</th>
            <th scope="col" className="px-4 py-2 font-medium">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {ROUTES.map((r) => (
            <tr key={r.route} className={r.status === "planned" ? "text-ink-muted" : ""}>
              <th scope="row" className="px-4 py-3 text-left font-semibold">{r.route}</th>
              <td className="px-4 py-3">
                {r.status === "available" ? <code className="font-dash-mono text-[12.5px]">{r.how}</code> : r.how}
              </td>
              <td className="px-4 py-3 whitespace-nowrap">
                <StatusBadge status={r.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Routes into TraceroAI and what comes out. Available routes carry traces
// (a navy packet travelling the line); planned ones are dashed and still.
const IN = [
  { label: "Python SDK", sub: "sync and async", live: true },
  { label: "HTTP API", sub: "POST /v1/traces", live: true, mono: true },
  { label: "Recovery agent", sub: "traceroai[recovery]", live: true, mono: true },
  { label: "OpenTelemetry", sub: "OTLP over HTTP", live: true },
  { label: "LangChain", sub: "via OpenInference", live: true },
  { label: "TypeScript SDK", sub: "Planned", live: false },
];
const OUT = [
  { label: "A diagnosis", sub: "per trace, with evidence" },
  { label: "Issues", sub: "failures grouped by cause" },
  { label: "Recovery runs", sub: "and experiments" },
];

export function RoutesDiagram() {
  const rowH = 52;
  const inY = (i: number) => 24 + i * rowH;
  const outY = (i: number) => 24 + (i + 1.5) * rowH;
  const core = { x: 360, y: 24 + 2 * rowH - 6, w: 230, h: rowH + 46 };
  const coreMid = core.y + core.h / 2;
  return (
    <figure className="hidden md:block">
      <svg viewBox="0 0 900 340" className="h-auto w-full" role="img" aria-labelledby="routes-title routes-desc">
        <title id="routes-title">How traces reach TraceroAI</title>
        <desc id="routes-desc">
          Traces arrive today from the Python SDK, the HTTP API, the recovery agent, and any app instrumented with
          OpenTelemetry, including LangChain through OpenInference. A TypeScript SDK is planned. TraceroAI turns each trace into a diagnosis, groups failures into issues, and
          records recovery runs and experiments.
        </desc>
        {IN.map((r, i) => {
          const y = inY(i) + 20;
          const d = `M 236 ${y} C 300 ${y}, 300 ${coreMid}, ${core.x} ${coreMid}`;
          return (
            <g key={r.label}>
              <rect x="4" y={inY(i)} width="232" height="40" rx="4" fill="var(--color-surface)" stroke={r.live ? "var(--color-line-strong)" : "var(--color-line-strong)"} strokeDasharray={r.live ? undefined : "4 4"} />
              <text x="18" y={inY(i) + 17} fontSize="13" fontWeight="600" fill={r.live ? "var(--color-ink)" : "var(--color-ink-muted)"}>
                {r.label}
              </text>
              <text x="18" y={inY(i) + 32} fontSize="11.5" fill="var(--color-ink-muted)" fontFamily={r.mono ? "var(--font-dash-mono)" : undefined}>
                {r.sub}
              </text>
              <path id={`route-${i}`} d={d} fill="none" stroke={r.live ? "var(--color-ink-muted)" : "var(--color-line-strong)"} strokeWidth="1.25" strokeDasharray={r.live ? undefined : "4 4"} />
              {r.live && (
                <circle r="3.5" fill="var(--color-accent)" className="arch-packet" opacity="0">
                  <animateMotion dur="2.6s" begin={`${i * 0.55}s`} repeatCount="indefinite" keyPoints="0;1;1" keyTimes="0;0.45;1" calcMode="linear">
                    <mpath href={`#route-${i}`} />
                  </animateMotion>
                  <animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;0.05;0.42;0.47;1" dur="2.6s" begin={`${i * 0.55}s`} repeatCount="indefinite" />
                </circle>
              )}
            </g>
          );
        })}
        <rect x={core.x} y={core.y} width={core.w} height={core.h} rx="6" fill="var(--color-accent)" />
        <text x={core.x + 20} y={core.y + 34} fontSize="17" fontWeight="700" fill="#ffffff">TraceroAI</text>
        <text x={core.x + 20} y={core.y + 56} fontSize="12" fill="#dbe4f0">checks every trace and</text>
        <text x={core.x + 20} y={core.y + 72} fontSize="12" fill="#dbe4f0">names the step that failed</text>
        {OUT.map((o, i) => {
          const y = outY(i) - 26 + 20;
          const d = `M ${core.x + core.w} ${coreMid} C ${core.x + core.w + 60} ${coreMid}, ${core.x + core.w + 60} ${y}, 664 ${y}`;
          return (
            <g key={o.label}>
              <path id={`out-${i}`} d={d} fill="none" stroke="var(--color-ink-muted)" strokeWidth="1.25" />
              <circle r="3.5" fill="var(--color-accent)" className="arch-packet" opacity="0">
                <animateMotion dur="2.6s" begin={`${1.2 + i * 0.4}s`} repeatCount="indefinite" keyPoints="0;1;1" keyTimes="0;0.4;1" calcMode="linear">
                  <mpath href={`#out-${i}`} />
                </animateMotion>
                <animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;0.05;0.37;0.42;1" dur="2.6s" begin={`${1.2 + i * 0.4}s`} repeatCount="indefinite" />
              </circle>
              <rect x="664" y={outY(i) - 26} width="232" height="40" rx="4" fill="var(--color-surface)" stroke="var(--color-line-strong)" />
              <text x="678" y={outY(i) - 9} fontSize="13" fontWeight="600" fill="var(--color-ink)">{o.label}</text>
              <text x="678" y={outY(i) + 6} fontSize="11.5" fill="var(--color-ink-muted)">{o.sub}</text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}
