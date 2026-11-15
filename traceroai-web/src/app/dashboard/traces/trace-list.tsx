import Link from "next/link";

import type { TraceSort } from "@/lib/api";
import type { Trace, TraceDiagnosis } from "@/lib/trace-types";

import { AutoSubmitSelect } from "../auto-submit-select";
import { SearchIcon } from "@/components/icons";
import {
  DiagnosisBadge,
  ProvenanceMark,
  StageSequence,
  diagnosisName,
  formatMs,
  formatWhen,
  hrefWith,
} from "../ui";

// Filtering, sorting and paging happen on the server: the filters are a plain
// GET form and the chips, column headers and page links are URLs, so the list
// works without JavaScript and every view can be linked to.

export type TraceListFilters = {
  project?: string;
  diagnosis?: string;
  q?: string;
  range?: string;
  model?: string;
  environment?: string;
  sort?: TraceSort;
  cursor?: string;
};

const DIAGNOSIS_LABELS = new Set<TraceDiagnosis>([
  "healthy_answer",
  "correct_refusal",
  "retrieval_miss",
  "unsupported_claim",
  "wrong_answer",
  "low_context_relevance",
  "needs_review",
]);

/** Only a real diagnosis label filters the list; anything else shows all. */
export function parseDiagnosis(value: string | undefined) {
  return value && DIAGNOSIS_LABELS.has(value as TraceDiagnosis) ? value : undefined;
}

export function parseSort(value: string | undefined): TraceSort | undefined {
  return value === "oldest" || value === "slowest" ? value : undefined;
}

/** The list filters as URL parameters (empty ones dropped by hrefWith). */
function params(filters: TraceListFilters) {
  return {
    project: filters.project,
    diagnosis: filters.diagnosis,
    q: filters.q,
    range: filters.range,
    model: filters.model,
    environment: filters.environment,
    sort: filters.sort,
  };
}

export function listHref(filters: TraceListFilters) {
  return hrefWith("/dashboard/traces", { ...params(filters), cursor: filters.cursor });
}

/** Link to a trace that keeps the list's filters, so the list beside it
 * shows the same traces in the same order. */
export function traceHref(traceId: string, filters: TraceListFilters) {
  return hrefWith(`/dashboard/traces/${encodeURIComponent(traceId)}`, params(filters));
}

export function shortId(traceId: string) {
  return traceId.slice(0, 8);
}

export function TraceFilters({
  filters,
  diagnosisCounts,
  models,
  environments,
}: {
  filters: TraceListFilters;
  diagnosisCounts: Record<string, number>;
  models: string[];
  environments: string[];
}) {
  // Changing a filter starts again from the first page.
  const base = { ...filters, cursor: undefined };
  const labels = Object.entries(diagnosisCounts).sort((a, b) => b[1] - a[1]);
  const all = Object.values(diagnosisCounts).reduce((s, n) => s + n, 0);
  const selectClass =
    "rounded border border-line-strong bg-surface py-1.5 pr-7 pl-2.5 text-sm hover:bg-sunken";

  return (
    <div className="flex flex-col gap-3">
      <form action="/dashboard/traces" method="get" role="search" className="flex flex-wrap items-center gap-2">
        {filters.project && <input type="hidden" name="project" value={filters.project} />}
        {filters.diagnosis && <input type="hidden" name="diagnosis" value={filters.diagnosis} />}
        {filters.range && <input type="hidden" name="range" value={filters.range} />}
        {filters.sort && <input type="hidden" name="sort" value={filters.sort} />}
        <label htmlFor="trace-search" className="sr-only">
          Search questions
        </label>
        <div className="flex min-w-0 flex-1 basis-64 items-center gap-2 rounded border border-line-strong bg-surface px-2.5 focus-within:outline-2 focus-within:outline-accent md:max-w-md">
          <SearchIcon className="shrink-0 text-ink-muted" />
          <input
            id="trace-search"
            type="search"
            name="q"
            defaultValue={filters.q}
            maxLength={200}
            placeholder="Search questions"
            className="w-full bg-transparent py-1.5 text-sm placeholder:text-ink-faint focus:outline-none"
          />
          <kbd className="hidden rounded-[3px] border border-line-strong px-1 font-dash-mono text-[11px] text-ink-muted sm:block" title="Press / to search">
            /
          </kbd>
        </div>
        {models.length > 1 && (
          <>
            <label htmlFor="filter-model" className="sr-only">
              Model
            </label>
            <AutoSubmitSelect id="filter-model" name="model" defaultValue={filters.model ?? ""} className={selectClass}>
              <option value="">All models</option>
              {models.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </AutoSubmitSelect>
          </>
        )}
        {environments.length > 1 && (
          <>
            <label htmlFor="filter-environment" className="sr-only">
              Environment
            </label>
            <AutoSubmitSelect
              id="filter-environment"
              name="environment"
              defaultValue={filters.environment ?? ""}
              className={selectClass}
            >
              <option value="">All environments</option>
              {environments.map((env) => (
                <option key={env} value={env}>
                  {env}
                </option>
              ))}
            </AutoSubmitSelect>
          </>
        )}
        <button
          type="submit"
          className="rounded border border-line-strong bg-surface px-3 py-1.5 text-sm font-medium hover:bg-sunken"
        >
          Search
        </button>
      </form>

      <nav aria-label="Filter by diagnosis">
        <ul className="flex flex-wrap gap-1.5">
          <li>
            <FilterChip active={!filters.diagnosis} href={listHref({ ...base, diagnosis: undefined })}>
              All <span className="text-ink-muted">{all.toLocaleString()}</span>
            </FilterChip>
          </li>
          {labels.map(([label, count]) => (
            <li key={label}>
              <FilterChip active={filters.diagnosis === label} href={listHref({ ...base, diagnosis: label })}>
                {diagnosisName(label)} <span className="text-ink-muted">{count.toLocaleString()}</span>
              </FilterChip>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}

function FilterChip({ active, href, children }: { active: boolean; href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      aria-current={active ? "true" : undefined}
      className={`inline-flex items-center gap-1.5 rounded border px-2.5 py-1 text-sm ${
        active
          ? "border-accent bg-accent-soft font-medium text-accent"
          : "border-line-strong bg-surface text-ink hover:bg-sunken"
      }`}
    >
      {children}
    </Link>
  );
}

/** A column header that sorts the list. Clicking an active header flips or
 * clears it. */
function SortHeader({
  label,
  filters,
  active,
  direction,
  next,
  align = "left",
  className = "",
}: {
  label: string;
  filters: TraceListFilters;
  active: boolean;
  direction: "ascending" | "descending";
  next: TraceSort;
  align?: "left" | "right";
  className?: string;
}) {
  return (
    <th
      scope="col"
      aria-sort={active ? direction : undefined}
      className={`px-3 py-2 font-medium ${align === "right" ? "text-right" : ""} ${className}`}
    >
      <Link
        href={listHref({ ...filters, cursor: undefined, sort: next === "newest" ? undefined : next })}
        className={`inline-flex items-center gap-1 hover:text-ink ${active ? "text-ink" : ""}`}
      >
        {label}
        <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" className={active ? "" : "opacity-40"}>
          {active && direction === "ascending" ? (
            <path d="M5 2 8.5 7h-7z" fill="currentColor" />
          ) : (
            <path d="M5 8 1.5 3h7z" fill="currentColor" />
          )}
        </svg>
        <span className="sr-only">
          {active ? `, sorted ${direction}; activate to change` : ", activate to sort"}
        </span>
      </Link>
    </th>
  );
}

/** The full trace table for the Traces page. */
export function TraceTable({ traces, filters }: { traces: Trace[]; filters: TraceListFilters }) {
  const sort = filters.sort ?? "newest";
  return (
    <div className="overflow-x-auto rounded border border-line">
      <table className="w-full min-w-[46rem] border-collapse text-sm">
        <caption className="sr-only">
          Traces,{" "}
          {sort === "slowest" ? "slowest first" : sort === "oldest" ? "oldest first" : "newest first"}
        </caption>
        <thead>
          <tr className="border-b border-line-strong bg-sunken text-left text-xs text-ink-muted">
            <th scope="col" className="w-24 py-2 pr-2 pl-4 font-medium">Trace</th>
            <th scope="col" className="px-3 py-2 font-medium">Question</th>
            <th scope="col" className="px-3 py-2 font-medium">Stages</th>
            <th scope="col" className="px-3 py-2 font-medium">Diagnosis</th>
            <th scope="col" className="px-3 py-2 font-medium max-xl:hidden">Model</th>
            <SortHeader
              label="Latency"
              filters={filters}
              active={sort === "slowest"}
              direction="descending"
              next={sort === "slowest" ? "newest" : "slowest"}
              align="right"
            />
            <SortHeader
              label="Time"
              filters={filters}
              active={sort !== "slowest"}
              direction={sort === "oldest" ? "ascending" : "descending"}
              next={sort === "newest" ? "oldest" : "newest"}
              align="right"
              className="pr-4"
            />
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {traces.map((trace) => (
            <tr key={trace.traceId} className="group relative hover:bg-sunken focus-within:bg-sunken">
              <td className="py-2.5 pr-2 pl-4 font-dash-mono text-xs text-ink-muted">{shortId(trace.traceId)}</td>
              <td className="max-w-0 px-3 py-2.5 w-[42%]">
                {/* The whole row is the link: this anchor's ::after covers it. */}
                <Link
                  href={traceHref(trace.traceId, filters)}
                  data-list-row
                  className="block truncate font-medium outline-none after:absolute after:inset-0 group-hover:underline focus-visible:underline focus-visible:after:outline-2 focus-visible:after:-outline-offset-2 focus-visible:after:outline-accent"
                >
                  {trace.query.original}
                </Link>
                {trace.recovery && (
                  <p className="mt-0.5 text-xs text-ink-muted">Recovery attempt {trace.recovery.attempt}</p>
                )}
              </td>
              <td className="px-3 py-2.5">
                <StageSequence trace={trace} />
              </td>
              <td className="px-3 py-2.5">
                <div className="flex items-center gap-1.5 whitespace-nowrap">
                  <DiagnosisBadge label={trace.diagnosis.label} size="sm" />
                  <ProvenanceMark source={trace.diagnosis.source} status={trace.deepStatus} size="sm" />
                </div>
              </td>
              <td className="px-3 py-2.5 whitespace-nowrap text-ink-muted max-xl:hidden">{trace.generation.model}</td>
              <td className="px-3 py-2.5 text-right whitespace-nowrap text-ink-muted">{formatMs(trace.latency.totalMs)}</td>
              <td className="py-2.5 pr-4 pl-3 text-right whitespace-nowrap text-ink-muted">{formatWhen(trace.timestamp)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Pager({ filters, nextCursor }: { filters: TraceListFilters; nextCursor: string | null }) {
  if (!filters.cursor && !nextCursor) return null;
  const base = { ...filters, cursor: undefined };
  const sort = filters.sort ?? "newest";
  return (
    <nav aria-label="Pages" className="flex justify-between text-sm">
      {filters.cursor ? (
        <Link href={listHref(base)} className="text-accent hover:underline">
          First page
        </Link>
      ) : (
        <span />
      )}
      {nextCursor && (
        <Link href={listHref({ ...base, cursor: nextCursor })} className="text-accent hover:underline">
          {sort === "newest" ? "Older traces" : sort === "oldest" ? "Newer traces" : "Faster traces"}
        </Link>
      )}
    </nav>
  );
}

/** The quieted list beside an open trace. */
export function TraceRailList({
  traces,
  selected,
  filters,
}: {
  traces: Trace[];
  selected: string;
  filters: TraceListFilters;
}) {
  const scope = [
    filters.diagnosis && diagnosisName(filters.diagnosis),
    filters.model,
    filters.environment,
    filters.q && `"${filters.q}"`,
  ].filter(Boolean);
  const order = filters.sort === "slowest" ? "Slowest first" : filters.sort === "oldest" ? "Oldest first" : "Latest first";
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-line px-4 py-3">
        <Link href={listHref(filters)} className="text-sm font-semibold hover:underline">
          Traces
        </Link>
        <p className="mt-0.5 truncate text-xs text-ink-muted">{[...scope, order].join(", ")}</p>
        <p className="mt-1 text-[11px] text-ink-muted">
          <kbd className="font-dash-mono">j</kbd> / <kbd className="font-dash-mono">k</kbd> next and previous
        </p>
      </div>
      {traces.length === 0 ? (
        <p className="px-4 py-6 text-sm text-ink-muted">No traces match these filters.</p>
      ) : (
        <TraceRows traces={traces} selected={selected} filters={filters} quiet className="flex-1 overflow-y-auto" />
      )}
    </div>
  );
}

/** Compact two-line rows: the list beside an open trace (quiet: unselected
 * rows recede), and the Traces page on phones. */
export function TraceRows({
  traces,
  filters,
  selected,
  quiet = false,
  className = "",
}: {
  traces: Trace[];
  filters: TraceListFilters;
  selected?: string;
  quiet?: boolean;
  className?: string;
}) {
  return (
    <ul className={`divide-y divide-line ${className}`}>
      {traces.map((trace) => {
        const on = trace.traceId === selected;
        return (
          <li key={trace.traceId}>
            <Link
              href={traceHref(trace.traceId, filters)}
              data-list-row
              aria-current={on ? "page" : undefined}
              className={`block px-4 py-2.5 focus-visible:-outline-offset-2 ${on ? "bg-accent-soft" : quiet ? "hover:bg-surface" : "hover:bg-sunken"}`}
            >
              <span
                className={`line-clamp-2 text-sm ${on ? "font-semibold text-ink" : quiet ? "text-ink-muted" : "font-medium"}`}
              >
                {trace.query.original}
              </span>
              <span className="mt-1.5 flex items-center gap-2 text-xs text-ink-muted">
                <StageSequence trace={trace} />
                <span className="truncate">{diagnosisName(trace.diagnosis.label)}</span>
                <span className="ml-auto shrink-0">
                  {filters.sort === "slowest" ? formatMs(trace.latency.totalMs) : formatWhen(trace.timestamp)}
                </span>
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
