import { getTraces } from "@/lib/api";

import { TraceList } from "./trace-list";

export default async function TracesPage() {
  const traces = await getTraces();

  return (
    <section>
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-cyan-300">
            Traces
          </p>
          <h1 className="mt-3 text-3xl font-semibold">RAG Trace Debugger</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-400">
            Inspect individual RAG requests and diagnose whether failures came
            from retrieval, context, prompting, or generation.
          </p>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 px-4 py-3">
          <p className="text-xs text-zinc-500">Total traces</p>
          <p className="mt-1 text-xl font-semibold">{traces.length}</p>
        </div>
      </div>

      <TraceList traces={traces} />
    </section>
  );
}