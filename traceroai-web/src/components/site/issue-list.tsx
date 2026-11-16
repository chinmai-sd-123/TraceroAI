// The issues page as it looks with the bundled demo data (30 recorded runs from
// the example app), seeded without a judge, so every diagnosis is an estimate.
// Rows are exactly what GET /v1/issues returned for that data.

const ISSUES = [
  { label: "Needs review", tone: "warn", key: "plans-and-limits", by: "top source", count: 4 },
  { label: "Needs review", tone: "warn", key: "refund-policy", by: "top source", count: 4 },
  { label: "Retrieval miss", tone: "cause", key: "refund-policy", by: "top source", count: 2 },
  { label: "Needs review", tone: "warn", key: "regions", by: "top source", count: 2 },
  { label: "Wrong answer", tone: "cause", key: "recovery_v1", by: "prompt version", count: 1 },
  { label: "Retrieval miss", tone: "cause", key: "plans-and-limits", by: "top source", count: 1 },
] as const;

export function IssueList() {
  return (
    <figure className="overflow-hidden rounded-md border border-line-strong bg-surface">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[30rem] border-collapse text-sm">
          <thead>
            <tr className="border-b border-line-strong bg-sunken text-left text-xs text-ink-muted">
              <th scope="col" className="px-4 py-2 font-medium">Issue</th>
              <th scope="col" className="px-4 py-2 font-medium">Grouped by</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Traces</th>
              <th scope="col" className="px-4 py-2 font-medium">State</th>
            </tr>
          </thead>
          <tbody className="rise-rows divide-y divide-line">
            {ISSUES.map((issue) => (
              <tr key={`${issue.label}-${issue.key}`}>
                <th scope="row" className="px-4 py-2.5 text-left font-normal">
                  <span className="inline-flex items-center gap-2">
                    <span
                      className={`hatch block h-2 w-5 ${issue.tone === "cause" ? "text-cause" : "text-warn"}`}
                      aria-hidden="true"
                    />
                    <span className={`font-semibold ${issue.tone === "cause" ? "text-cause" : "text-warn"}`}>{issue.label}</span>
                    <span className="font-dash-mono text-[12.5px] text-ink-muted">{issue.key}</span>
                  </span>
                </th>
                <td className="px-4 py-2.5 text-ink-muted">{issue.by}</td>
                <td className="px-4 py-2.5 text-right font-semibold tabular-nums">{issue.count}</td>
                <td className="px-4 py-2.5 text-ink-muted">Open</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <figcaption className="border-t border-line px-4 py-2.5 text-sm text-ink-muted">
        <span className="font-semibold text-ink">Figure 1.</span> The bundled demo data: of 30 recorded runs, the 14 that failed become six
        issues. It was seeded without a judge, so these diagnoses are estimates (hatched).
      </figcaption>
    </figure>
  );
}
