import Link from "next/link";

import { getEvalRuns } from "@/lib/api";

import { EmptyState, PageFrame, PageHeader, Panel, formatMs, formatWhen } from "../ui";

export default async function EvalRunsPage({
  searchParams,
}: {
  searchParams: Promise<{ project?: string }>;
}) {
  const { project } = await searchParams;
  const { regressionRuns, experimentRuns } = await getEvalRuns(project);
  const isEmpty = regressionRuns.length === 0 && experimentRuns.length === 0;

  return (
    <PageFrame>
      <PageHeader
        title="Eval runs"
        description="Experiments compare pipeline settings on a labelled dataset; regression runs check the diagnoses still hold."
      />

      {isEmpty && (
        <div className="mt-6">
          <EmptyState title={`No eval runs yet${project ? ` in ${project}` : ""}`}>
            Run one from your own pipeline with{" "}
            <code className="font-dash-mono text-[0.8125rem] text-ink">traceroai.eval.run_experiment</code>.{" "}
            <Link href="/docs#experiments" className="text-accent underline">
              See how
            </Link>
            .
          </EmptyState>
        </div>
      )}

      <div className="mt-6 space-y-6">
        {experimentRuns.map((run) => {
          const ranked = [...run.values].sort((a, b) => b.healthyRate - a.healthyRate);
          return (
            <Panel
              key={run.id}
              title={
                <Link href={`/dashboard/eval-runs/${run.id}`} className="hover:underline">
                  {run.experimentName}
                </Link>
              }
              description={
                <>
                  Experiment on <code className="font-dash-mono text-[0.8125rem] text-ink">{run.comparedParameter}</code>,{" "}
                  {run.values.length} variants · {formatWhen(run.timestamp)}
                </>
              }
              actions={
                <Link href={`/dashboard/eval-runs/${run.id}`} className="text-sm text-accent hover:underline">
                  Open
                </Link>
              }
              flush
            >
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-y border-line-strong bg-sunken text-left text-xs text-ink-muted">
                    <th scope="col" className="px-5 py-2 font-medium">{run.comparedParameter}</th>
                    <th scope="col" className="px-3 py-2 font-medium">Healthy answers</th>
                    <th scope="col" className="px-5 py-2 text-right font-medium">Average latency</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {ranked.map((v) => {
                    const recommended = v.value === run.recommendation.value;
                    return (
                      <tr key={v.value}>
                        <td className="px-5 py-2.5 font-dash-mono text-[0.8125rem]">
                          {v.value}
                          {recommended && (
                            <span className="ml-2 rounded-[3px] border border-pass px-1 font-dash text-xs font-semibold text-pass">
                              Recommended
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2.5">
                          <span className="flex items-center gap-3">
                            <span className="h-2 w-40 bg-sunken max-sm:w-20">
                              <span className={`block h-2 ${recommended ? "bg-pass" : "bg-ink-muted/45"}`} style={{ width: `${v.healthyRate}%` }} />
                            </span>
                            {v.healthyRate}%
                          </span>
                        </td>
                        <td className="px-5 py-2.5 text-right text-ink-muted">{formatMs(v.avgLatencyMs)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <p className="border-t border-line px-5 py-3 text-sm text-ink-muted">{run.recommendation.reason}</p>
            </Panel>
          );
        })}

        {regressionRuns.length > 0 && (
          <Panel title="Regression runs" description="Labelled cases replayed against a pipeline version." flush>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[40rem] border-collapse text-sm">
                <thead>
                  <tr className="border-y border-line-strong bg-sunken text-left text-xs text-ink-muted">
                    <th scope="col" className="px-5 py-2 font-medium">Pipeline</th>
                    <th scope="col" className="px-3 py-2 font-medium">Dataset</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Passed</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Retrieval</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Failure labels</th>
                    <th scope="col" className="px-5 py-2 text-right font-medium">Run</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {regressionRuns.map((run) => (
                    <tr key={run.id} className="group relative hover:bg-sunken">
                      <td className="px-5 py-2.5 font-medium">
                        <Link href={`/dashboard/eval-runs/${run.id}`} className="after:absolute after:inset-0 group-hover:underline">
                          {run.pipelineVersion}
                        </Link>
                      </td>
                      <td className="px-3 py-2.5 text-ink-muted">{run.datasetName}</td>
                      <td className={`px-3 py-2.5 text-right font-semibold ${run.summary.failedCases === 0 ? "text-pass" : ""}`}>
                        {run.summary.passedCases}/{run.summary.totalCases}
                      </td>
                      <td className="px-3 py-2.5 text-right text-ink-muted">{run.summary.retrievalAccuracy}%</td>
                      <td className="px-3 py-2.5 text-right text-ink-muted">{run.summary.failureLabelAccuracy}%</td>
                      <td className="px-5 py-2.5 text-right whitespace-nowrap text-ink-muted">{formatWhen(run.timestamp)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        )}
      </div>
    </PageFrame>
  );
}
