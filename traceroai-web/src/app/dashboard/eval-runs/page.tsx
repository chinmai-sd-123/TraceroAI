import Link from "next/link";

import { getEvalRuns } from "@/lib/api";

export default async function EvalRunsPage() {
  const { regressionRuns, experimentRuns } = await getEvalRuns();
  return (
    <section>
      <div>
        <p className="text-sm font-medium uppercase tracking-[0.18em] text-cyan-300">
          Eval Runs
        </p>
        <h1 className="mt-3 text-3xl font-semibold">RAG Evaluation Runs</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-400">
          Track regression quality and compare retrieval or prompting
          configurations before shipping pipeline changes.
        </p>
      </div>

      <div className="mt-8 grid gap-6">
        <section>
          <h2 className="text-lg font-semibold">Regression Runs</h2>
          <div className="mt-4 grid gap-4">
            {regressionRuns.map((run) => (
              <Link
                key={run.id}
                href={`/dashboard/eval-runs/${run.id}`}
                className="block rounded-lg border border-zinc-800 bg-zinc-900/60 p-6 transition hover:border-zinc-700 hover:bg-zinc-900"
              >
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <p className="text-sm font-semibold">{run.pipelineVersion}</p>
                    <p className="mt-1 text-sm text-zinc-500">
                      Dataset: {run.datasetName}
                    </p>
                  </div>

                  <span className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-sm font-medium text-emerald-300">
                    {run.summary.passedCases}/{run.summary.totalCases} passed
                  </span>
                </div>

                <div className="mt-6 grid gap-4 md:grid-cols-5">
                  <Metric label="Overall" value={`${run.summary.overallAccuracy}%`} />
                  <Metric label="Status" value={`${run.summary.statusAccuracy}%`} />
                  <Metric
                    label="Retrieval"
                    value={`${run.summary.retrievalAccuracy}%`}
                  />
                  <Metric
                    label="Failure labels"
                    value={`${run.summary.failureLabelAccuracy}%`}
                  />
                  <Metric label="Avg latency" value={`${run.summary.avgLatencyMs}ms`} />
                </div>
              </Link>
            ))}
          </div>
        </section>

        <section>
          <h2 className="text-lg font-semibold">Experiment Runs</h2>
          <div className="mt-4 grid gap-4">
            {experimentRuns.map((run) => (
              <Link
                key={run.id}
                href={`/dashboard/eval-runs/${run.id}`}
                className="block rounded-lg border border-zinc-800 bg-zinc-900/60 p-6 transition hover:border-zinc-700 hover:bg-zinc-900"
              >
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <p className="text-sm font-semibold">{run.experimentName}</p>
                    <p className="mt-1 text-sm text-zinc-500">
                      Compared parameter: {run.comparedParameter}
                    </p>
                  </div>

                  <span className="rounded-md border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-sm font-medium text-cyan-300">
                    Recommended: {run.comparedParameter}={run.recommendation.value}
                  </span>
                </div>

                <div className="mt-6 overflow-hidden rounded-lg border border-zinc-800">
                  <div className="grid grid-cols-5 bg-zinc-950 px-4 py-3 text-xs font-medium uppercase tracking-wide text-zinc-500">
                    <div>Value</div>
                    <div>Healthy</div>
                    <div>Recall</div>
                    <div>Precision</div>
                    <div>Latency</div>
                  </div>

                  <div className="divide-y divide-zinc-800">
                    {run.values.map((value) => (
                      <div
                        key={value.value}
                        className="grid grid-cols-5 px-4 py-3 text-sm text-zinc-300"
                      >
                        <div className="font-mono">{value.value}</div>
                        <div>{value.healthyRate}%</div>
                        <div>{value.sourceRecallRate}%</div>
                        <div>{value.contextPrecision}%</div>
                        <div>{value.avgLatencyMs}ms</div>
                      </div>
                    ))}
                  </div>
                </div>

                <p className="mt-4 text-sm leading-6 text-zinc-400">
                  {run.recommendation.reason}
                </p>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-4">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="mt-2 text-lg font-semibold">{value}</p>
    </div>
  );
}
