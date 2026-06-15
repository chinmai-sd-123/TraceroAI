export default function DashboardPage() {
  return (
    <section>
      <div>
        <p className="text-sm font-medium uppercase tracking-[0.18em] text-cyan-300">
          Dashboard
        </p>
        <h1 className="mt-3 text-3xl font-semibold">RAG Reliability Overview</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-400">
          Monitor trace volume, failure patterns, evaluation quality, and latency
          across RAG pipeline runs.
        </p>
      </div>

      <div className="mt-8 grid gap-4 md:grid-cols-4">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-sm text-zinc-500">Total traces</p>
          <p className="mt-2 text-2xl font-semibold">0</p>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-sm text-zinc-500">Healthy rate</p>
          <p className="mt-2 text-2xl font-semibold">--</p>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-sm text-zinc-500">Avg latency</p>
          <p className="mt-2 text-2xl font-semibold">--</p>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-sm text-zinc-500">Open failures</p>
          <p className="mt-2 text-2xl font-semibold">0</p>
        </div>
      </div>
    </section>
  );
}