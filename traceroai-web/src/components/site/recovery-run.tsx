import { ArrowRightIcon } from "@/components/icons";

// The recovery run the hero's case belongs to (example app): trace 5f7bf901
// was attempt 2. Values are the run's own, as the dashboard shows them.

const ATTEMPTS = [
  { title: "Original attempt", id: "bfe5cdc6", verdict: "Unsupported claim", healthy: false, took: "1.76 s" },
  { title: "Attempt 2", id: "5f7bf901", verdict: "Unsupported claim", healthy: false, took: "1.68 s", here: true },
  { title: "Attempt 3", id: null, verdict: "Healthy answer", healthy: true, took: "1.94 s" },
];

export function RecoveryRun() {
  return (
    <figure className="overflow-hidden rounded-md border border-line-strong bg-surface">
      <ol className="rise-rows" aria-label="Recovery run, attempt by attempt">
        {ATTEMPTS.map((a, i) => (
          <li key={a.title}>
            {i > 0 && (
              <p className="flex items-center gap-2 border-t border-dashed border-line px-5 py-2 text-xs text-ink-muted">
                <ArrowRightIcon size={13} className="rotate-90 text-ink-faint" />
                The agent regenerated with a stricter prompt
              </p>
            )}
            <div
              className={`grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 border-t border-line px-5 py-3.5 first:border-t-0 sm:grid-cols-[12.5rem_minmax(0,1fr)_auto] ${
                a.healthy ? "bg-pass-soft" : ""
              }`}
            >
              <p className="text-sm">
                <span className="font-medium">{a.title}</span>
                {a.id && <span className="ml-2 font-dash-mono text-xs text-ink-muted">{a.id}</span>}
              </p>
              <p className="flex flex-wrap items-center gap-x-3 gap-y-1 max-sm:col-span-2 max-sm:row-start-2">
                <span className={`font-semibold ${a.healthy ? "text-pass" : "text-cause"}`}>{a.verdict}</span>
                {a.here && (
                  <span className="inline-flex items-center gap-1.5 text-xs text-cause">
                    <span className="size-1.5 rounded-full bg-cause" aria-hidden="true" />
                    The case at the top of this page
                  </span>
                )}
              </p>
              <p className="flex items-center gap-2 text-xs whitespace-nowrap text-ink-muted max-sm:col-start-2 max-sm:row-start-1">
                <span className="rounded-[3px] border border-ink px-1 py-px font-semibold text-ink">Final</span>
                top_k 3 · {a.took}
              </p>
            </div>
          </li>
        ))}
      </ol>
      <figcaption className="border-t border-line px-5 py-2.5 text-sm text-ink-muted">
        <span className="font-semibold text-ink">Figure 2.</span> One recovery run, attempt by attempt. The third answer was
        healthy.
      </figcaption>
    </figure>
  );
}
