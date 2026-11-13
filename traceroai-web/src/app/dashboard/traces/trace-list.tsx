import Link from "next/link";

import { sourceLabel } from "@/components/diagnosis-provenance";
import type { MockTrace, TraceDiagnosis } from "@/lib/mock-traces";

// Filtering and paging happen on the server: the search box is a plain GET
// form and the chips and page links are URLs, so the list works without
// JavaScript and every filtered view can be linked to.

const diagnosisStyles: Record<TraceDiagnosis, string> = {
  healthy_answer: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  correct_refusal: "border-sky-500/30 bg-sky-500/10 text-sky-300",
  retrieval_miss: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  unsupported_claim: "border-red-500/30 bg-red-500/10 text-red-300",
  wrong_answer: "border-red-500/30 bg-red-500/10 text-red-300",
  low_context_relevance: "border-orange-500/30 bg-orange-500/10 text-orange-300",
  needs_review: "border-zinc-500/30 bg-zinc-500/10 text-zinc-300",
};

export type TraceListFilters = {
  project?: string;
  diagnosis?: string;
  q?: string;
  cursor?: string;
};

function formatLabel(label: string) {
  return label.replaceAll("_", " ");
}

function formatTime(timestamp: string) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(timestamp));
}

function href(filters: TraceListFilters) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value);
  }
  const query = params.toString();
  return query ? `/dashboard/traces?${query}` : "/dashboard/traces";
}

export function TraceList({
  traces,
  nextCursor,
  filters,
  diagnosisCounts,
}: {
  traces: MockTrace[];
  nextCursor: string | null;
  filters: TraceListFilters;
  diagnosisCounts: Record<string, number>;
}) {
  // Changing a filter starts again from the first page.
  const base = { project: filters.project, q: filters.q, diagnosis: filters.diagnosis };
  const labels = Object.entries(diagnosisCounts).sort((a, b) => b[1] - a[1]);

  return (
    <div>
      <div className="mt-8 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <form action="/dashboard/traces" method="get" className="flex w-full gap-2 md:max-w-md">
          {filters.project && <input type="hidden" name="project" value={filters.project} />}
          {filters.diagnosis && (
            <input type="hidden" name="diagnosis" value={filters.diagnosis} />
          )}
          <label htmlFor="trace-search" className="sr-only">
            Search queries
          </label>
          <input
            id="trace-search"
            type="search"
            name="q"
            defaultValue={filters.q}
            maxLength={200}
            placeholder="Search queries…"
            className="w-full rounded-md border border-zinc-800 bg-zinc-950/60 px-4 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-zinc-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/40"
          />
          <button
            type="submit"
            className="rounded-md border border-zinc-700 px-4 py-2 text-sm text-zinc-300 transition hover:border-zinc-500 hover:text-zinc-100"
          >
            Search
          </button>
        </form>

        <div className="flex flex-wrap gap-2">
          <FilterChip active={!filters.diagnosis} href={href({ ...base, diagnosis: undefined })}>
            All
          </FilterChip>
          {labels.map(([label, count]) => (
            <FilterChip
              key={label}
              active={filters.diagnosis === label}
              href={href({ ...base, diagnosis: label })}
            >
              {formatLabel(label)} <span className="text-zinc-500">{count}</span>
            </FilterChip>
          ))}
        </div>
      </div>

      <p className="mt-4 text-xs text-zinc-500">
        {traces.length === 0
          ? "No traces match these filters."
          : `Showing ${traces.length} trace${traces.length === 1 ? "" : "s"}${
              filters.cursor ? " (later page)" : ""
            }, newest first`}
      </p>

      <div className="mt-3 overflow-x-auto rounded-lg border border-zinc-800">
        <div className="grid min-w-[760px] grid-cols-[1.4fr_120px_150px_110px_110px_110px] border-b border-zinc-800 bg-zinc-950 px-4 py-3 text-xs font-medium uppercase tracking-wide text-zinc-500">
          <div>Query</div>
          <div>Status</div>
          <div>Diagnosis</div>
          <div>Model</div>
          <div>Latency</div>
          <div>Time</div>
        </div>

        <div className="min-w-[760px] divide-y divide-zinc-800">
          {traces.map((trace) => (
            <Link
              key={trace.traceId}
              href={`/dashboard/traces/${trace.traceId}`}
              className="grid grid-cols-[1.4fr_120px_150px_110px_110px_110px] items-center bg-zinc-900/40 px-4 py-4 transition hover:bg-zinc-900"
            >
              <div className="pr-4">
                <p className="line-clamp-1 text-sm font-medium text-zinc-100">
                  {trace.query.original}
                </p>
                <p className="mt-1 line-clamp-1 text-xs text-zinc-500">
                  {trace.recovery && (
                    <span className="mr-2 rounded bg-violet-500/15 px-1.5 py-0.5 font-medium text-violet-300">
                      recovery · attempt {trace.recovery.attempt}
                    </span>
                  )}
                  {trace.retrieval.strategy}
                </p>
              </div>

              <div className="text-xs text-zinc-400">
                {trace.status ? formatLabel(trace.status) : "—"}
              </div>

              <div>
                <span
                  className={`inline-flex rounded-md border px-2 py-1 text-xs font-medium ${diagnosisStyles[trace.diagnosis.label]}`}
                >
                  {formatLabel(trace.diagnosis.label)}
                </span>
                {sourceLabel(trace.diagnosis.source) && (
                  <p
                    className={`mt-1 text-[11px] ${
                      trace.diagnosis.source === "judge" ? "text-violet-300" : "text-zinc-500"
                    }`}
                  >
                    {sourceLabel(trace.diagnosis.source)}
                  </p>
                )}
              </div>

              <div className="text-sm text-zinc-400">{trace.generation.model}</div>

              <div className="font-mono text-sm text-zinc-300">
                {trace.latency.totalMs > 0 ? `${trace.latency.totalMs}ms` : "—"}
              </div>

              <div className="text-sm text-zinc-500">{formatTime(trace.timestamp)}</div>
            </Link>
          ))}
        </div>
      </div>

      {(filters.cursor || nextCursor) && (
        <nav aria-label="Pages" className="mt-4 flex justify-between text-sm">
          {filters.cursor ? (
            <Link href={href(base)} className="text-zinc-400 transition hover:text-zinc-100">
              ← Newest
            </Link>
          ) : (
            <span />
          )}
          {nextCursor && (
            <Link
              href={href({ ...base, cursor: nextCursor })}
              className="text-zinc-400 transition hover:text-zinc-100"
            >
              Older →
            </Link>
          )}
        </nav>
      )}
    </div>
  );
}

function FilterChip({
  active,
  href,
  children,
}: {
  active: boolean;
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`rounded-md border px-3 py-1.5 text-xs font-medium transition ${
        active
          ? "border-cyan-400/40 bg-cyan-400/10 text-cyan-200"
          : "border-zinc-800 bg-zinc-900/60 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200"
      }`}
    >
      {children}
    </Link>
  );
}
