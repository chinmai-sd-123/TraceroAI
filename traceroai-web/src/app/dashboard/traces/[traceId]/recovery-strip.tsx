import Link from "next/link";

import { getTraces } from "@/lib/api";
import type { Trace } from "@/lib/trace-types";

import { ArrowRightIcon } from "@/components/icons";
import { diagnosisName, isHealthy } from "../../ui";
import { RECOVERY_ACTIONS } from "../../recovery-runs/recovery";

/** When this trace is one attempt of a recovery run: every attempt of the run
 * in order, with the agent's decision between them. */
export async function RecoveryStrip({ trace }: { trace: Trace }) {
  const recovery = trace.recovery!;
  if (!recovery.runId) {
    return (
      <p className="mt-4 text-sm text-ink-muted">
        Attempt {recovery.attempt} of a recovery run. This trace came from an SDK older than 0.5, which didn&apos;t
        record the run id, so its other attempts can&apos;t be linked.
      </p>
    );
  }
  const { traces } = await getTraces({ recoveryRunId: recovery.runId, sort: "oldest", limit: 20 });
  const attempts = (traces.length > 0 ? traces : [trace])
    .filter((t) => t.recovery)
    .sort((a, b) => a.recovery!.attempt - b.recovery!.attempt);

  return (
    <nav aria-label="Recovery run" className="mt-4 rounded border border-line bg-sunken px-4 py-3">
      <p className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
        <span>
          <span className="font-semibold">Recovery run</span>{" "}
          <span className="text-ink-muted">
            attempt {recovery.attempt} of {attempts.length}
          </span>
        </span>
        <Link href={`/dashboard/recovery-runs/${encodeURIComponent(recovery.runId)}`} className="text-accent hover:underline">
          Open the run
        </Link>
      </p>
      <ol className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-2 text-sm">
        {attempts.map((a, i) => {
          const current = a.traceId === trace.traceId;
          const healthy = isHealthy(a.diagnosis.label);
          return (
            <li key={a.traceId} className="flex items-center gap-2">
              {i > 0 && (
                <span className="flex items-center gap-1.5 text-xs text-ink-muted">
                  <ArrowRightIcon size={12} />
                  {RECOVERY_ACTIONS[a.recovery!.action ?? ""] ?? "retried"}
                  <ArrowRightIcon size={12} />
                </span>
              )}
              <Link
                href={`/dashboard/traces/${a.traceId}`}
                aria-current={current ? "page" : undefined}
                className={`rounded border px-2 py-0.5 ${
                  current ? "border-accent bg-surface font-semibold" : "border-line-strong bg-surface hover:bg-rail"
                }`}
              >
                {a.recovery!.attempt}.{" "}
                <span className={healthy ? "text-pass" : ""}>{diagnosisName(a.diagnosis.label)}</span>
              </Link>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
