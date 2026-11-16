import Link from "next/link";

import type { Issue, IssueStatus } from "@/lib/api";

import { DiagnosisBadge, diagnosisName, formatWhen, hrefWith } from "../ui";
import { IssueButton } from "./issue-button";

const STATUS: Record<IssueStatus, { word: string; className: string; note: (i: Issue) => string | null }> = {
  regressed: {
    word: "Regressed",
    className: "border-warn bg-warn-soft text-warn",
    note: (i) =>
      `${i.countSinceResolved} new failure${i.countSinceResolved === 1 ? "" : "s"} since it was resolved ${formatWhen(i.resolvedAt ?? i.lastSeen)}`,
  },
  open: { word: "Open", className: "border-accent/40 bg-accent-soft text-accent", note: () => null },
  resolved: {
    word: "Resolved",
    className: "border-pass/40 bg-pass-soft text-pass",
    note: (i) => (i.resolvedAt ? `Resolved ${formatWhen(i.resolvedAt)}; no failures since` : null),
  },
};

export function issueTitle(issue: Issue) {
  return `${diagnosisName(issue.label)} on ${issue.source}`;
}

export function issueTracesHref(issue: Issue) {
  return hrefWith("/dashboard/traces", { project: issue.projectId, issue: issue.issueKey });
}

export function StatusChip({ status }: { status: IssueStatus }) {
  const s = STATUS[status];
  return (
    <span className={`inline-flex h-6 items-center rounded-[3px] border px-2 text-xs font-semibold ${s.className}`}>
      {s.word}
    </span>
  );
}

/** Issues as rows: what failed and where, how often, and when. */
export function IssueList({ issues, compact = false }: { issues: Issue[]; compact?: boolean }) {
  return (
    <ul className="divide-y divide-line">
      {issues.map((issue) => {
        const note = STATUS[issue.status].note(issue);
        return (
          <li
            key={`${issue.projectId}|${issue.issueKey}`}
            className={`grid gap-x-6 gap-y-3 px-5 py-4 ${compact ? "sm:grid-cols-[minmax(0,1fr)_auto]" : "md:grid-cols-[minmax(0,1fr)_11rem_auto]"}`}
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <StatusChip status={issue.status} />
                <DiagnosisBadge label={issue.label} size="sm" />
                <span className="text-sm text-ink-muted">top source</span>
                <code className="truncate font-dash-mono text-[0.8125rem] text-ink">{issue.source}</code>
              </div>
              <Link href={issueTracesHref(issue)} className="mt-2 block text-[15px] leading-6 hover:underline">
                {issue.recentQuestions.map((q) => `“${q.trim()}”`).join(", ")}
                {issue.questions > issue.recentQuestions.length && (
                  <span className="text-ink-muted"> and {issue.questions - issue.recentQuestions.length} more</span>
                )}
              </Link>
              {note && <p className="mt-1 text-sm text-ink-muted">{note}</p>}
            </div>
            {!compact && (
              <dl className="grid grid-cols-2 gap-x-4 text-sm md:block md:space-y-1">
                <div>
                  <dt className="sr-only">Failing traces</dt>
                  <dd>
                    <span className="font-semibold tabular-nums">{issue.count}</span>{" "}
                    <span className="text-ink-muted">trace{issue.count === 1 ? "" : "s"}</span>
                  </dd>
                </div>
                <div>
                  <dt className="sr-only">Last seen</dt>
                  <dd className="text-ink-muted">
                    last seen{" "}
                    <time dateTime={issue.lastSeen} className="whitespace-nowrap">
                      {formatWhen(issue.lastSeen)}
                    </time>
                  </dd>
                </div>
              </dl>
            )}
            <div className="flex items-start gap-3 sm:justify-end">
              {compact ? (
                <span className="pt-1 text-sm text-ink-muted tabular-nums">
                  {issue.count} trace{issue.count === 1 ? "" : "s"}
                </span>
              ) : (
                <IssueButton
                  projectId={issue.projectId}
                  issueKey={issue.issueKey}
                  resolved={issue.status === "resolved"}
                  title={issueTitle(issue)}
                />
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
