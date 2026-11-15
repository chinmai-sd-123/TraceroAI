import Link from "next/link";

import { TIME_RANGES, getRecoveryRuns, parseRange } from "@/lib/api";

import { ArrowRightIcon } from "@/components/icons";
import { DiagnosisBadge, EmptyState, PageFrame, PageHeader, Segmented, formatWhen, hrefWith, isHealthy } from "../ui";
import { actionWords } from "./recovery";

export default async function RecoveryRunsPage({
  searchParams,
}: {
  searchParams: Promise<{ project?: string; range?: string }>;
}) {
  const { project, range: rawRange } = await searchParams;
  const range = parseRange(rawRange, "all");
  const runs = await getRecoveryRuns(project, { range, limit: 100 });
  const ended = runs?.filter((r) => r.finalDiagnosis && isHealthy(r.finalDiagnosis)).length ?? 0;

  return (
    <PageFrame>
      <PageHeader
        title="Recovery runs"
        description="Each time the RecoveryAgent retried a failing answer: what failed, what it changed, and how it ended."
        actions={
          <Segmented
            label="Time range"
            active={range}
            options={Object.keys(TIME_RANGES).map((key) => ({
              key,
              label: key === "all" ? "All" : key,
              href: hrefWith("/dashboard/recovery-runs", { project, range: key === "all" ? undefined : key }),
            }))}
          />
        }
      />

      <div className="mt-6">
        {runs === null ? (
          <EmptyState title="Couldn't load recovery runs">The API didn&apos;t answer; check the banner above.</EmptyState>
        ) : runs.length === 0 ? (
          <EmptyState title="No recovery runs yet">
            Wrap your pipeline in the SDK&apos;s <code className="font-dash-mono text-[0.8125rem] text-ink">RecoveryAgent</code>{" "}
            and every retry it makes shows up here as one run.{" "}
            <Link href="/docs#recovery" className="text-accent underline">
              See how
            </Link>
            .
          </EmptyState>
        ) : (
          <>
            <p className="mb-3 text-sm text-ink-muted">
              {runs.length} run{runs.length === 1 ? "" : "s"}; {ended} ended with a healthy answer.
            </p>
            <div className="overflow-x-auto rounded border border-line">
              <table className="w-full min-w-[44rem] border-collapse text-sm">
                <caption className="sr-only">Recovery runs, most recent first</caption>
                <thead>
                  <tr className="border-b border-line-strong bg-sunken text-left text-xs text-ink-muted">
                    <th scope="col" className="px-4 py-2 font-medium">Question</th>
                    <th scope="col" className="px-3 py-2 font-medium">Attempts</th>
                    <th scope="col" className="px-3 py-2 font-medium">Outcome</th>
                    <th scope="col" className="px-4 py-2 text-right font-medium">Last attempt</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {runs.map((run) => {
                    const healthy = run.finalDiagnosis ? isHealthy(run.finalDiagnosis) : false;
                    return (
                      <tr key={run.runId} className="group relative hover:bg-sunken">
                        <td className="max-w-0 px-4 py-3 w-[40%]">
                          <Link
                            href={`/dashboard/recovery-runs/${encodeURIComponent(run.runId)}`}
                            className="block truncate font-medium after:absolute after:inset-0 group-hover:underline"
                          >
                            {run.question}
                          </Link>
                          <p className="mt-0.5 font-dash-mono text-xs text-ink-muted">{run.runId.slice(0, 8)}</p>
                        </td>
                        <td className="px-3 py-3">
                          <ol className="flex flex-wrap items-center gap-1.5 text-xs text-ink-muted">
                            {run.diagnoses.map((d, i) => (
                              <li key={i} className="flex items-center gap-1.5">
                                {i > 0 && (
                                  <span title={actionWords(run.actions[i])} className="flex items-center">
                                    <ArrowRightIcon size={12} />
                                    <span className="sr-only">{actionWords(run.actions[i])}, then</span>
                                  </span>
                                )}
                                {d ? <DiagnosisBadge label={d} size="sm" /> : <span>pending</span>}
                              </li>
                            ))}
                          </ol>
                        </td>
                        <td className="px-3 py-3 whitespace-nowrap">
                          <span className={`font-semibold ${healthy ? "text-pass" : ""}`}>
                            {healthy
                              ? run.attempts === 1
                                ? "Healthy first time"
                                : `Healthy after ${run.attempts}`
                              : `Still failing after ${run.attempts}`}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right whitespace-nowrap text-ink-muted">{formatWhen(run.endedAt)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </PageFrame>
  );
}
