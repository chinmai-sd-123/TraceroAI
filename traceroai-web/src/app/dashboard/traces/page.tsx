import { TIME_RANGES, getSummary, getTraces, parseRange, rangeSince } from "@/lib/api";

import { ListKeys } from "../list-keys";
import Link from "next/link";

import { EmptyState, PageFrame, PageHeader, Segmented, diagnosisName } from "../ui";
import {
  Pager,
  TraceFilters,
  TraceRows,
  TraceTable,
  type TraceListFilters,
  listHref,
  parseDiagnosis,
  parseSort,
} from "./trace-list";

const PAGE_SIZE = 50;

export default async function TracesPage({
  searchParams,
}: {
  searchParams: Promise<{
    project?: string;
    diagnosis?: string;
    q?: string;
    cursor?: string;
    range?: string;
    model?: string;
    environment?: string;
    sort?: string;
    issue?: string;
  }>;
}) {
  const params = await searchParams;
  const range = parseRange(params.range, "all");
  const filters: TraceListFilters = {
    project: params.project,
    diagnosis: parseDiagnosis(params.diagnosis),
    q: params.q?.trim() || undefined,
    range: range === "all" ? undefined : range,
    model: params.model || undefined,
    environment: params.environment || undefined,
    sort: parseSort(params.sort),
    cursor: params.cursor,
    issue: params.issue?.slice(0, 2000) || undefined,
  };
  const narrowed = Boolean(filters.model || filters.environment);

  const [page, scopeSummary, filteredSummary] = await Promise.all([
    getTraces({
      projectId: filters.project,
      diagnosis: filters.diagnosis,
      q: filters.q,
      model: filters.model,
      environment: filters.environment,
      sort: filters.sort,
      cursor: filters.cursor,
      issueKey: filters.issue,
      limit: PAGE_SIZE,
      since: rangeSince(range),
    }),
    // Model and environment options come from the whole range, so picking one
    // doesn't hide the others; diagnosis counts follow the picked ones.
    getSummary(filters.project, range),
    narrowed
      ? getSummary(filters.project, range, { model: filters.model, environment: filters.environment })
      : Promise.resolve(null),
  ]);
  const counts = (filteredSummary ?? scopeSummary)?.byDiagnosis ?? {};
  const byCount = (record: Record<string, number> | undefined) =>
    Object.entries(record ?? {})
      .sort((a, b) => b[1] - a[1])
      .map(([name]) => name);

  const order = filters.sort === "slowest" ? "slowest first" : filters.sort === "oldest" ? "oldest first" : "newest first";

  return (
    <PageFrame>
      <ListKeys />
      <PageHeader
        title="Traces"
        description="Every answer your pipeline logged, with the stage that broke. Open one to see the evidence."
        actions={
          <Segmented
            label="Time range"
            active={range}
            options={Object.keys(TIME_RANGES).map((key) => ({
              key,
              label: key === "all" ? "All" : key,
              href: listHref({ ...filters, cursor: undefined, range: key === "all" ? undefined : key }),
            }))}
          />
        }
      />

      <div className="mt-5 space-y-4">
        {filters.issue && (
          <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded border border-line bg-sunken px-4 py-2.5 text-sm">
            <span>
              Showing one issue:{" "}
              <strong className="font-semibold">{diagnosisName(filters.issue.split("|")[0])}</strong>, top source{" "}
              <code className="font-dash-mono text-[0.8125rem]">{filters.issue.split("|").slice(1).join("|")}</code>
            </span>
            <Link href={listHref({ ...filters, issue: undefined, cursor: undefined })} className="text-accent hover:underline">
              Show all traces
            </Link>
          </p>
        )}
        <TraceFilters
          filters={filters}
          diagnosisCounts={counts}
          models={byCount(scopeSummary?.byModel)}
          environments={byCount(scopeSummary?.byEnvironment)}
        />
        {page.traces.length === 0 ? (
          <EmptyState title="No traces match these filters">
            {filters.diagnosis || filters.q || narrowed || range !== "all"
              ? "Clear a filter or widen the time range."
              : "Send a trace with the Python SDK and it appears here."}
          </EmptyState>
        ) : (
          <>
            <p className="text-xs text-ink-muted">
              {page.traces.length} trace{page.traces.length === 1 ? "" : "s"}
              {filters.cursor ? " on this page" : ""}, {order}. Stages run Retrieval, Grounding, Answer;
              red marks the probable cause, hatching an estimate. Press <kbd className="font-dash-mono">j</kbd>{" "}
              and <kbd className="font-dash-mono">k</kbd> to move through the list.
            </p>
            <div className="max-md:hidden">
              <TraceTable traces={page.traces} filters={filters} />
            </div>
            <TraceRows traces={page.traces} filters={filters} className="rounded border border-line md:hidden" />
            <Pager filters={filters} nextCursor={page.nextCursor} />
          </>
        )}
      </div>
    </PageFrame>
  );
}
