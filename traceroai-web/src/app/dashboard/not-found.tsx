import Link from "next/link";

export default function DashboardNotFound() {
  return (
    <section className="flex min-h-[50vh] flex-col items-center justify-center text-center">
      <p className="text-sm font-medium uppercase tracking-[0.18em] text-cyan-300">
        404
      </p>
      <h1 className="mt-3 text-3xl font-semibold">Not found</h1>
      <p className="mt-3 max-w-md text-sm leading-6 text-zinc-400">
        This trace or eval run doesn’t exist, or the API isn’t reachable. It may
        have been removed, or the ID is wrong.
      </p>
      <div className="mt-6 flex gap-3">
        <Link
          href="/dashboard/traces"
          className="rounded-md border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-100"
        >
          Browse traces
        </Link>
        <Link
          href="/dashboard"
          className="rounded-md bg-cyan-300 px-4 py-2 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-200"
        >
          Back to overview
        </Link>
      </div>
    </section>
  );
}
