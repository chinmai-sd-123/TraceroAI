import type { TimeBucket } from "@/lib/api";

import { formatMs } from "./ui";

// Small server-rendered charts. Bars are HTML so they stay crisp at any width;
// the latency line is SVG with a non-scaling stroke. Every chart carries a text
// summary for screen readers, and each bar a tooltip with its numbers.

function bucketLabel(start: string, bucket: "hour" | "day"): string {
  const date = new Date(start);
  return bucket === "hour"
    ? new Intl.DateTimeFormat("en", { hour: "2-digit", minute: "2-digit" }).format(date)
    : new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(date);
}

function AxisLabels({ buckets, bucket }: { buckets: TimeBucket[]; bucket: "hour" | "day" }) {
  if (buckets.length === 0) return null;
  const middle = buckets[Math.floor(buckets.length / 2)];
  return (
    <div className="mt-1.5 flex justify-between text-[11px] text-ink-muted" aria-hidden="true">
      <span>{bucketLabel(buckets[0].start, bucket)}</span>
      {buckets.length > 4 && <span>{bucketLabel(middle.start, bucket)}</span>}
      <span>{bucketLabel(buckets[buckets.length - 1].start, bucket)}</span>
    </div>
  );
}

/** Traces per bucket, healthy stacked under the rest. */
export function VolumeChart({
  buckets,
  bucket,
  height = 160,
}: {
  buckets: TimeBucket[];
  bucket: "hour" | "day";
  height?: number;
}) {
  const max = Math.max(1, ...buckets.map((b) => b.total));
  const total = buckets.reduce((s, b) => s + b.total, 0);
  const healthy = buckets.reduce((s, b) => s + b.healthy, 0);
  return (
    <figure>
      <div className="flex gap-3">
        <div className="flex flex-col justify-between text-right text-[11px] text-ink-muted" style={{ height }} aria-hidden="true">
          <span>{max}</span>
          <span>0</span>
        </div>
        <div
          role="img"
          aria-label={`${total} traces in this range, ${healthy} healthy, ${total - healthy} not healthy.`}
          className="relative flex flex-1 items-end gap-px border-b border-l border-line-strong"
          style={{ height }}
        >
          <span className="pointer-events-none absolute inset-x-0 top-0 border-t border-dashed border-line" aria-hidden="true" />
          {buckets.map((b) => (
            <span
              key={b.start}
              title={`${bucketLabel(b.start, bucket)}: ${b.total} traces, ${b.healthy} healthy`}
              className="flex h-full min-w-0 flex-1 flex-col justify-end hover:bg-sunken"
            >
              <span className="block bg-ink-muted/55" style={{ height: `${((b.total - b.healthy) / max) * 100}%` }} />
              <span className="block bg-pass" style={{ height: `${(b.healthy / max) * 100}%` }} />
            </span>
          ))}
        </div>
      </div>
      <div className="pl-8">
        <AxisLabels buckets={buckets} bucket={bucket} />
      </div>
      <figcaption className="mt-3 flex gap-4 text-xs text-ink-muted">
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-[1px] bg-pass" aria-hidden="true" /> Healthy
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-[1px] bg-ink-muted/55" aria-hidden="true" /> Not healthy
        </span>
      </figcaption>
    </figure>
  );
}

/** p95 latency per bucket as a line; buckets without measured traces leave gaps. */
export function LatencyChart({
  buckets,
  bucket,
  height = 160,
}: {
  buckets: TimeBucket[];
  bucket: "hour" | "day";
  height?: number;
}) {
  const values = buckets.map((b) => b.p95Ms);
  const measured = values.filter((v): v is number => v != null);
  if (measured.length === 0) {
    return (
      <p className="flex items-center justify-center text-sm text-ink-muted" style={{ height }}>
        No latency measured in this range.
      </p>
    );
  }
  const max = Math.max(...measured) * 1.1;
  const n = buckets.length;
  const x = (i: number) => (n === 1 ? 50 : (i / (n - 1)) * 100);
  const y = (v: number) => 100 - (v / max) * 100;
  // Split into runs of consecutive measured buckets.
  const runs: Array<Array<[number, number]>> = [];
  values.forEach((v, i) => {
    if (v == null) return;
    const last = runs[runs.length - 1];
    if (last && values[i - 1] != null) last.push([x(i), y(v)]);
    else runs.push([[x(i), y(v)]]);
  });
  return (
    <figure>
      <div className="flex gap-3">
        <div className="flex w-12 shrink-0 flex-col justify-between text-right text-[11px] text-ink-muted" style={{ height }} aria-hidden="true">
          <span>{formatMs(max)}</span>
          <span>0</span>
        </div>
        <div
          role="img"
          aria-label={`p95 latency ranged from ${formatMs(Math.min(...measured))} to ${formatMs(Math.max(...measured))}.`}
          className="relative flex-1 border-b border-l border-line-strong"
          style={{ height }}
        >
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 size-full overflow-visible" aria-hidden="true">
            {runs.map((run, i) =>
              run.length === 1 ? (
                <line key={i} x1={run[0][0]} y1={run[0][1]} x2={run[0][0]} y2={run[0][1]} stroke="var(--color-accent)" strokeWidth={5} strokeLinecap="round" vectorEffect="non-scaling-stroke" />
              ) : (
                <polyline
                  key={i}
                  points={run.map(([px, py]) => `${px},${py}`).join(" ")}
                  fill="none"
                  stroke="var(--color-accent)"
                  strokeWidth={1.75}
                  strokeLinejoin="round"
                  vectorEffect="non-scaling-stroke"
                />
              ),
            )}
          </svg>
          <div className="absolute inset-0 flex">
            {buckets.map((b) => (
              <span
                key={b.start}
                className="h-full flex-1 hover:bg-sunken/60"
                title={`${bucketLabel(b.start, bucket)}: p95 ${b.p95Ms == null ? "not measured" : formatMs(b.p95Ms)}`}
              />
            ))}
          </div>
        </div>
      </div>
      <div className="pl-[3.75rem]">
        <AxisLabels buckets={buckets} bucket={bucket} />
      </div>
    </figure>
  );
}

/** A metric's recent history, drawn small beside its value. */
export function MiniBars({
  values,
  tone = "ink",
}: {
  values: Array<number | null>;
  tone?: "ink" | "pass";
}) {
  const max = Math.max(1, ...values.map((v) => v ?? 0));
  return (
    <span className="flex h-7 items-end gap-px" aria-hidden="true">
      {values.map((v, i) => (
        <span
          key={i}
          className={`block min-w-px flex-1 ${v == null ? "bg-line" : tone === "pass" ? "bg-pass/70" : "bg-ink-muted/45"}`}
          style={{ height: v == null ? "1px" : `${Math.max(4, (v / max) * 100)}%` }}
        />
      ))}
    </span>
  );
}
