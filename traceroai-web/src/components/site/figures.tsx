import Image from "next/image";
import type { ReactNode } from "react";

import { Magnify, Reveal } from "./motion";

/** A numbered figure: a real dashboard screenshot in a ruled frame, linking
 * to the full-size image. width/height are the image's CSS size; the files
 * are captured at twice that for sharp screens. */
export function Figure({
  n,
  src,
  alt,
  width,
  height,
  children,
  priority = false,
  sizes = "(min-width: 1024px) 50vw, 100vw",
}: {
  n: number;
  src: string;
  alt: string;
  width: number;
  height: number;
  children: ReactNode;
  priority?: boolean;
  sizes?: string;
}) {
  return (
    <Reveal>
      <figure className="overflow-hidden rounded border border-line-strong bg-surface">
        <a href={src} className="block" aria-label={`Open figure ${n} full size`}>
          <Magnify>
            <Image
              src={src}
              alt={alt}
              width={width * 2}
              height={height * 2}
              priority={priority}
              sizes={sizes}
              className="magnify-image h-auto w-full"
            />
          </Magnify>
        </a>
        <figcaption className="border-t border-line px-4 py-2.5 text-sm text-ink-muted">
          <span className="font-semibold text-ink">Figure {n}.</span> {children}
        </figcaption>
      </figure>
    </Reveal>
  );
}

type Box = { x: number; y: number; label: string; sub: string; dashed?: boolean };

const BOXES: Record<string, Box> = {
  app: { x: 20, y: 56, label: "Your RAG app", sub: "with the traceroai SDK" },
  api: { x: 330, y: 56, label: "API", sub: "FastAPI · quick checks on ingest" },
  db: { x: 640, y: 56, label: "Postgres", sub: "traces, verdicts, eval runs" },
  dash: { x: 20, y: 216, label: "Dashboard", sub: "Next.js · reads with a server key" },
  queue: { x: 330, y: 216, label: "Redis stream", sub: "evaluation queue" },
  worker: { x: 640, y: 216, label: "Worker", sub: "embeddings and LLM judge" },
  llm: { x: 640, y: 372, label: "Your LLM provider", sub: "only if you set a key", dashed: true },
};
const W = 240;
const H = 64;

function Arrow({
  id,
  d,
  label,
  lx,
  ly,
  dashed,
  flow,
}: {
  id: string;
  d: string;
  label?: string;
  lx?: number;
  ly?: number;
  dashed?: boolean;
  flow?: { begin: string; color: string }; // a packet travelling the path
}) {
  return (
    <g>
      <path id={id} d={d} fill="none" stroke="var(--color-ink-muted)" strokeWidth="1.5" strokeDasharray={dashed ? "5 4" : undefined} markerEnd="url(#arrow)" />
      {flow && (
        <circle r="4.5" fill={flow.color} className="arch-packet" opacity="0">
          {/* One 3.2s cycle: travel the path in the first 30%, then fade. */}
          <animateMotion dur="3.2s" begin={flow.begin} repeatCount="indefinite" keyPoints="0;1;1" keyTimes="0;0.3;1" calcMode="linear">
            <mpath href={`#${id}`} />
          </animateMotion>
          <animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;0.04;0.28;0.34;1" dur="3.2s" begin={flow.begin} repeatCount="indefinite" />
        </circle>
      )}
      {label && (
        <text x={lx} y={ly} fontSize="13" fill="var(--color-ink-muted)" textAnchor="middle">
          {label}
        </text>
      )}
    </g>
  );
}

/** What runs where, as built: everything inside the dashed line is yours. */
export function ArchitectureDiagram() {
  return (
    <figure>
      <svg viewBox="0 0 900 460" className="hidden h-auto w-full md:block" role="img" aria-labelledby="arch-title arch-desc">
        <title id="arch-title">TraceroAI architecture</title>
        <desc id="arch-desc">
          Your app sends traces through the SDK to the API, which stores them in Postgres and queues them on a Redis stream.
          A worker evaluates queued traces, calling your LLM provider only if you configured a key, and writes verdicts back
          to Postgres. The dashboard reads from the API.
        </desc>
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0 0 10 5 0 10z" fill="var(--color-ink-muted)" />
          </marker>
        </defs>
        <rect x="4" y="10" width="892" height="320" rx="6" fill="var(--color-rail)" stroke="var(--color-line-strong)" strokeDasharray="6 5" />
        <text x="20" y="36" fontSize="13" fontWeight="600" fill="var(--color-ink-muted)">
          Your infrastructure
        </text>
        {Object.entries(BOXES).map(([key, b]) => (
          <g key={key}>
            <rect
              x={b.x}
              y={b.y}
              width={W}
              height={H}
              rx="4"
              fill="var(--color-surface)"
              stroke={b.dashed ? "var(--color-ink-muted)" : "var(--color-line-strong)"}
              strokeDasharray={b.dashed ? "5 4" : undefined}
            />
            <text x={b.x + 16} y={b.y + 27} fontSize="15" fontWeight="600" fill="var(--color-ink)">
              {b.label}
            </text>
            <text x={b.x + 16} y={b.y + 47} fontSize="12.5" fill="var(--color-ink-muted)">
              {b.sub}
            </text>
          </g>
        ))}
        {/* Packets follow one trace through the stack, in order. */}
        <Arrow id="a-ingest" d="M260 88 H326" label="traces" lx={293} ly={80} flow={{ begin: "0s", color: "var(--color-accent)" }} />
        <Arrow id="a-store" d="M570 88 H636" label="store" lx={603} ly={80} flow={{ begin: "0.4s", color: "var(--color-accent)" }} />
        <Arrow id="a-queue" d="M450 120 V212" label="queue" lx={478} ly={170} flow={{ begin: "0.5s", color: "var(--color-accent)" }} />
        <Arrow id="a-work" d="M570 248 H636" flow={{ begin: "0.9s", color: "var(--color-accent)" }} />
        <Arrow id="a-judge" d="M760 280 V368" label="judge calls" lx={808} ly={330} dashed flow={{ begin: "1.1s", color: "var(--color-ink-muted)" }} />
        <Arrow id="a-verdict" d="M760 212 V124" label="verdicts" lx={798} ly={170} flow={{ begin: "1.3s", color: "var(--color-pass)" }} />
        <Arrow id="a-read" d="M260 248 C 300 248, 300 120, 326 104" label="reads" lx={300} ly={182} />
      </svg>
      <ol className="space-y-2 text-sm md:hidden">
        <li><span className="font-semibold">Your RAG app</span> sends traces with the SDK to the <span className="font-semibold">API</span>.</li>
        <li>The API runs quick checks, stores the trace in <span className="font-semibold">Postgres</span> and queues it on a <span className="font-semibold">Redis stream</span>.</li>
        <li>A <span className="font-semibold">worker</span> runs embeddings and the LLM judge, calling <span className="font-semibold">your LLM provider</span> only if you set a key, and writes verdicts back.</li>
        <li>The <span className="font-semibold">dashboard</span> reads everything from the API.</li>
      </ol>
    </figure>
  );
}
