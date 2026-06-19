"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import type { MockTrace, TraceDiagnosis } from "@/lib/mock-traces";

const diagnosisStyles: Record<TraceDiagnosis, string> = {
  healthy_answer: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  correct_refusal: "border-sky-500/30 bg-sky-500/10 text-sky-300",
  retrieval_miss: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  unsupported_claim: "border-red-500/30 bg-red-500/10 text-red-300",
  wrong_answer: "border-red-500/30 bg-red-500/10 text-red-300",
  low_context_relevance: "border-orange-500/30 bg-orange-500/10 text-orange-300",
  needs_review: "border-zinc-500/30 bg-zinc-500/10 text-zinc-300",
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

export function TraceList({
  traces,
  initialDiagnosis = "all",
}: {
  traces: MockTrace[];
  initialDiagnosis?: "all" | TraceDiagnosis;
}) {
  const [search, setSearch] = useState("");
  const [diagnosis, setDiagnosis] = useState<"all" | TraceDiagnosis>(
    initialDiagnosis,
  );

  // Diagnosis labels actually present in the data, for the filter chips.
  const presentDiagnoses = useMemo(() => {
    const labels = new Set<TraceDiagnosis>();
    for (const trace of traces) {
      labels.add(trace.diagnosis.label);
    }
    return Array.from(labels);
  }, [traces]);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return traces.filter((trace) => {
      const matchesDiagnosis = diagnosis === "all" || trace.diagnosis.label === diagnosis;
      const matchesSearch = !query || trace.query.original.toLowerCase().includes(query);
      return matchesDiagnosis && matchesSearch;
    });
  }, [traces, search, diagnosis]);

  return (
    <div>
      <div className="mt-8 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <input
          type="text"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search queries…"
          className="w-full rounded-md border border-zinc-800 bg-zinc-950/60 px-4 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-zinc-600 focus:outline-none md:max-w-sm"
        />

        <div className="flex flex-wrap gap-2">
          <FilterChip active={diagnosis === "all"} onClick={() => setDiagnosis("all")}>
            All
          </FilterChip>
          {presentDiagnoses.map((label) => (
            <FilterChip
              key={label}
              active={diagnosis === label}
              onClick={() => setDiagnosis(label)}
            >
              {formatLabel(label)}
            </FilterChip>
          ))}
        </div>
      </div>

      <p className="mt-4 text-xs text-zinc-500">
        Showing {filtered.length} of {traces.length} traces
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
          {filtered.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-zinc-500">
              No traces match your filters.
            </p>
          ) : (
            filtered.map((trace) => (
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
                </div>

                <div className="text-sm text-zinc-400">{trace.generation.model}</div>

                <div className="font-mono text-sm text-zinc-300">
                  {trace.latency.totalMs > 0 ? `${trace.latency.totalMs}ms` : "—"}
                </div>

                <div className="text-sm text-zinc-500">
                  {formatTime(trace.timestamp)}
                </div>
              </Link>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md border px-3 py-1.5 text-xs font-medium transition ${
        active
          ? "border-cyan-400/40 bg-cyan-400/10 text-cyan-200"
          : "border-zinc-800 bg-zinc-900/60 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200"
      }`}
    >
      {children}
    </button>
  );
}