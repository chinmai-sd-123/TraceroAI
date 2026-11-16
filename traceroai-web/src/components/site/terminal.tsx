"use client";

import { useEffect, useState } from "react";

import { CopyButton } from "@/components/copy-button";

import { useInView, usePrefersReducedMotion } from "./motion";
import { GITHUB_URL } from "@/lib/links";

// The two commands that start TraceroAI with demo data, typed once when the
// terminal scrolls into view. Comments say what happens; no output is invented.

const LINES = [
  { kind: "cmd", text: `git clone ${GITHUB_URL}.git && cd TraceroAI` },
  { kind: "cmd", text: "docker compose -f infra/docker-compose.yml --profile demo up --build" },
  { kind: "note", text: "# API on http://localhost:8000, dashboard on http://localhost:3000" },
  { kind: "note", text: "# --profile demo adds 30 recorded runs to a project called demo" },
] as const;

// Where each line starts in the typed text.
const OFFSETS = LINES.map((_, i) => LINES.slice(0, i).reduce((n, l) => n + l.text.length, 0));

const COPY = `git clone ${GITHUB_URL}.git && cd TraceroAI\ndocker compose -f infra/docker-compose.yml --profile demo up --build`;

export function Terminal() {
  const reduced = usePrefersReducedMotion();
  const [ref, seen] = useInView<HTMLDivElement>(0.5);
  const [chars, setChars] = useState(0);
  const total = LINES.reduce((n, l) => n + l.text.length, 0);

  useEffect(() => {
    if (!seen || reduced || chars >= total) return;
    const id = setTimeout(() => setChars((c) => Math.min(total, c + 3)), 18);
    return () => clearTimeout(id);
  }, [seen, reduced, chars, total]);

  const shown = reduced ? total : chars;

  return (
    <div ref={ref} className="overflow-hidden rounded-md border border-ink bg-ink text-[#e6ebf2]">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-2 text-xs text-[#9aa6b6]">
        <span className="flex items-center gap-1.5" aria-hidden="true">
          <span className="size-2.5 rounded-full bg-white/15" />
          <span className="size-2.5 rounded-full bg-white/15" />
          <span className="size-2.5 rounded-full bg-white/15" />
        </span>
        <span>Terminal</span>
        <CopyButton text={COPY} tone="dark" />
      </div>
      <p className="sr-only">{LINES.map((l) => l.text).join(". ")}</p>
      <pre className="overflow-x-auto px-5 py-4 font-dash-mono text-[13px] leading-7" aria-hidden="true">
        {LINES.map((line, i) => {
          const budget = shown - OFFSETS[i];
          const visible = line.text.slice(0, Math.max(0, budget));
          const typingHere = budget > 0 && budget < line.text.length;
          if (!visible && i > 0) return null;
          return (
            <div key={i} className={line.kind === "note" ? "text-[#8b97a8]" : ""}>
              {line.kind === "cmd" && <span className="text-[#7f8ea3] select-none">$ </span>}
              {visible}
              {typingHere && <span className="term-caret" aria-hidden="true" />}
            </div>
          );
        })}
        {shown >= total && (
          <div>
            <span className="text-[#7f8ea3] select-none">$ </span>
            <span className="term-caret" aria-hidden="true" />
          </div>
        )}
      </pre>
    </div>
  );
}
