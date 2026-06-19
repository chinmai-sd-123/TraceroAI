"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surface the error for debugging; in production this is where a real
    // error reporter (Sentry, etc.) would hook in.
    console.error(error);
  }, [error]);

  return (
    <section className="flex min-h-[50vh] flex-col items-center justify-center text-center">
      <p className="text-sm font-medium uppercase tracking-[0.18em] text-amber-300">
        Something went wrong
      </p>
      <h1 className="mt-3 text-3xl font-semibold">Couldn’t load this page</h1>
      <p className="mt-3 max-w-md text-sm leading-6 text-zinc-400">
        An unexpected error occurred while rendering the dashboard. This is often
        a transient API hiccup — try again.
      </p>
      {error.digest && (
        <p className="mt-2 font-mono text-xs text-zinc-600">ref: {error.digest}</p>
      )}
      <div className="mt-6 flex gap-3">
        <button
          type="button"
          onClick={reset}
          className="rounded-md bg-cyan-300 px-4 py-2 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-200"
        >
          Try again
        </button>
        <Link
          href="/dashboard"
          className="rounded-md border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-100"
        >
          Back to overview
        </Link>
      </div>
    </section>
  );
}
