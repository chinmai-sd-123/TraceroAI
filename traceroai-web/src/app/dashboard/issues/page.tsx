import Link from "next/link";

import { TIME_RANGES, getIssues, parseRange } from "@/lib/api";

import { EmptyState, LinkTabs, PageFrame, PageHeader, Segmented, hrefWith } from "../ui";
import { IssueList } from "./issue-list";

type View = "attention" | "resolved" | "all";

export default async function IssuesPage({
  searchParams,
}: {
  searchParams: Promise<{ project?: string; range?: string; view?: string }>;
}) {
  const { project, range: rawRange, view: rawView } = await searchParams;
  const range = parseRange(rawRange, "all");
  const view: View = rawView === "resolved" || rawView === "all" ? rawView : "attention";
  const issues = await getIssues(project, { range, limit: 200 });

  const attention = issues?.filter((i) => i.status !== "resolved") ?? [];
  const resolved = issues?.filter((i) => i.status === "resolved") ?? [];
  const shown = view === "attention" ? attention : view === "resolved" ? resolved : (issues ?? []);
  const regressed = attention.filter((i) => i.status === "regressed").length;
  const href = (params: { view?: View; range?: string }) =>
    hrefWith("/dashboard/issues", {
      project,
      range: params.range ?? (range === "all" ? undefined : range),
      view: (params.view ?? view) === "attention" ? undefined : (params.view ?? view),
    });

  return (
    <PageFrame>
      <PageHeader
        title="Issues"
        description="Failing traces grouped by cause: retrieval failures by the top source the retriever returned, grounding and answer failures by prompt version. Resolve an issue once it's fixed; if it fails again, it comes back as regressed."
        actions={
          <Segmented
            label="Time range"
            active={range}
            options={Object.keys(TIME_RANGES).map((key) => ({
              key,
              label: key === "all" ? "All" : key,
              href: href({ range: key === "all" ? "" : key }),
            }))}
          />
        }
      />

      <div className="mt-5">
        <LinkTabs
          label="Issue status"
          active={view}
          tabs={[
            { key: "attention", label: `Needs attention ${attention.length}`, href: href({ view: "attention" }) },
            { key: "resolved", label: `Resolved ${resolved.length}`, href: href({ view: "resolved" }) },
            { key: "all", label: `All ${issues?.length ?? 0}`, href: href({ view: "all" }) },
          ]}
        />
      </div>

      <div className="mt-5">
        {issues === null ? (
          <EmptyState title="Couldn't load issues">The API didn&apos;t answer; check the banner above.</EmptyState>
        ) : shown.length === 0 ? (
          <EmptyState title={view === "resolved" ? "Nothing resolved yet" : "No failing traces in this range"}>
            {view === "resolved" ? (
              "Resolve an issue once its cause is fixed. If it fails again it comes back here as regressed."
            ) : (
              <>
                Every trace in this range was healthy, or nothing has been sent yet.{" "}
                <Link href="/docs/instrument/python-sdk" className="text-accent underline">
                  Send traces
                </Link>
                .
              </>
            )}
          </EmptyState>
        ) : (
          <>
            {view === "attention" && (
              <p className="mb-3 text-sm text-ink-muted">
                {attention.length} issue{attention.length === 1 ? "" : "s"}
                {regressed > 0 ? `, ${regressed} regressed after being resolved` : ""}. Most recently seen first.
              </p>
            )}
            <div className="rounded border border-line bg-surface">
              <IssueList issues={shown} />
            </div>
          </>
        )}
      </div>
    </PageFrame>
  );
}
