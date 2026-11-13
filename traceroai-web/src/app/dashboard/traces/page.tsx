import type { TraceDiagnosis } from "@/lib/mock-traces";
import { getProjects, getSummary, getTraces } from "@/lib/api";

import { ProjectSelector } from "./project-selector";
import { TraceList } from "./trace-list";

const PAGE_SIZE = 50;

const DIAGNOSIS_LABELS = new Set<TraceDiagnosis>([
  "healthy_answer",
  "correct_refusal",
  "retrieval_miss",
  "unsupported_claim",
  "wrong_answer",
  "low_context_relevance",
  "needs_review",
]);

export default async function TracesPage({
  searchParams,
}: {
  searchParams: Promise<{ project?: string; diagnosis?: string; q?: string; cursor?: string }>;
}) {
  const params = await searchParams;
  // Only honor a diagnosis filter that is a real label (links from the dashboard
  // Failure Mix pass these); anything else shows all.
  const diagnosis =
    params.diagnosis && DIAGNOSIS_LABELS.has(params.diagnosis as TraceDiagnosis)
      ? params.diagnosis
      : undefined;
  const q = params.q?.trim() || undefined;

  const [page, projects, summary] = await Promise.all([
    getTraces({
      projectId: params.project,
      diagnosis,
      q,
      cursor: params.cursor,
      limit: PAGE_SIZE,
    }),
    getProjects(),
    getSummary(params.project),
  ]);

  return (
    <section>
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-cyan-300">
            Traces
          </p>
          <h1 className="mt-3 text-3xl font-semibold">RAG Trace Debugger</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-400">
            Inspect individual RAG requests and diagnose whether failures came
            from retrieval, context, prompting, or generation.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {projects.length > 0 && (
            <ProjectSelector projects={projects} selected={params.project} />
          )}
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 px-4 py-3">
            <p className="text-xs text-zinc-500">Total traces</p>
            <p className="mt-1 text-xl font-semibold">{summary?.total ?? "--"}</p>
          </div>
        </div>
      </div>

      <TraceList
        traces={page.traces}
        nextCursor={page.nextCursor}
        filters={{ project: params.project, diagnosis, q, cursor: params.cursor }}
        diagnosisCounts={summary?.byDiagnosis ?? {}}
      />
    </section>
  );
}
