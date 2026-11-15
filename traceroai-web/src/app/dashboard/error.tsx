"use client";

import Link from "next/link";
import { useEffect } from "react";

import { AlertIcon } from "@/components/icons";
import { PageFrame } from "./ui";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surface the error for debugging; an error reporter would hook in here.
    console.error(error);
  }, [error]);

  return (
    <PageFrame>
      <div role="alert" className="mx-auto mt-10 max-w-lg rounded border border-warn/40 bg-warn-soft px-6 py-6">
        <h1 className="flex items-center gap-2 text-lg font-semibold">
          <AlertIcon className="text-warn" />
          This page couldn&apos;t load
        </h1>
        <p className="mt-2 text-sm leading-6">
          Something failed while reading from the API. It is often a passing problem, so try again; if it
          keeps happening, check the API&apos;s logs.
        </p>
        {error.digest && <p className="mt-2 font-dash-mono text-xs text-ink-muted">Reference {error.digest}</p>}
        <div className="mt-5 flex gap-2">
          <button
            type="button"
            onClick={reset}
            className="rounded bg-accent px-3.5 py-1.5 text-sm font-medium text-white hover:bg-accent/90"
          >
            Try again
          </button>
          <Link href="/dashboard" className="rounded border border-line-strong bg-surface px-3.5 py-1.5 text-sm font-medium hover:bg-sunken">
            Go to the overview
          </Link>
        </div>
      </div>
    </PageFrame>
  );
}
