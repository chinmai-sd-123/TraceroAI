import Link from "next/link";

import { PageFrame } from "./ui";

export default function DashboardNotFound() {
  return (
    <PageFrame>
      <div className="mx-auto mt-10 max-w-lg rounded border border-line px-6 py-6">
        <h1 className="text-lg font-semibold">Nothing with that id</h1>
        <p className="mt-2 text-sm leading-6 text-ink-muted">
          No trace or eval run here has that id. Check that it was copied whole, that it belongs to a
          project this dashboard can read, and that it hasn&apos;t passed the retention period.
        </p>
        <div className="mt-5 flex gap-2">
          <Link href="/dashboard/traces" className="rounded bg-accent px-3.5 py-1.5 text-sm font-medium text-white hover:bg-accent/90">
            Browse traces
          </Link>
          <Link href="/dashboard" className="rounded border border-line-strong bg-surface px-3.5 py-1.5 text-sm font-medium hover:bg-sunken">
            Go to the overview
          </Link>
        </div>
      </div>
    </PageFrame>
  );
}
