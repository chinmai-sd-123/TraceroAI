"use client";

import { useState, useTransition } from "react";

import { changeIssue } from "./actions";

/** Resolve an issue, or open a resolved one again. */
export function IssueButton({
  projectId,
  issueKey,
  resolved,
  title,
}: {
  projectId: string;
  issueKey: string;
  resolved: boolean; // the issue is resolved now: the button reopens it
  title: string; // for the accessible name, e.g. "Retrieval miss on refunds.md"
}) {
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const action = resolved ? "Reopen" : "Resolve";

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        disabled={pending}
        aria-label={`${action} ${title}`}
        onClick={() =>
          start(async () => {
            setError(null);
            const result = await changeIssue(projectId, issueKey, !resolved);
            if (!result.ok) setError(result.error);
          })
        }
        className={`h-8 rounded border px-3 text-sm font-medium transition-colors duration-150 disabled:cursor-wait disabled:opacity-60 ${
          resolved
            ? "border-line-strong bg-surface text-ink hover:bg-sunken"
            : "border-accent bg-accent text-white hover:bg-accent/90"
        }`}
      >
        {pending ? (resolved ? "Reopening" : "Resolving") : action}
      </button>
      {error && (
        <p role="alert" className="max-w-56 text-right text-xs text-warn">
          {error}
        </p>
      )}
    </div>
  );
}
