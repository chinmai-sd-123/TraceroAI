"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState, type ComponentType, type FormEvent } from "react";

import {
  ChevronLeftIcon,
  CodeIcon,
  DocsIcon,
  EvalRunsIcon,
  IssuesIcon,
  OverviewIcon,
  RecoveryIcon,
  SearchIcon,
  SignOutIcon,
  TracesIcon,
} from "@/components/icons";

import { logout } from "../login/actions";

type Section = { label: string; href: string; icon: ComponentType<{ className?: string }> };

const GROUPS: Array<{ name?: string; items: Section[] }> = [
  {
    items: [
      { label: "Overview", href: "/dashboard", icon: OverviewIcon },
      { label: "Issues", href: "/dashboard/issues", icon: IssuesIcon },
      { label: "Traces", href: "/dashboard/traces", icon: TracesIcon },
      { label: "Recovery runs", href: "/dashboard/recovery-runs", icon: RecoveryIcon },
    ],
  },
  {
    name: "Evaluate",
    items: [{ label: "Eval runs", href: "/dashboard/eval-runs", icon: EvalRunsIcon }],
  },
];

const ALL = GROUPS.flatMap((g) => g.items);

// Overview matches exactly (every dashboard path starts with /dashboard);
// the others match their section so detail pages stay highlighted too.
function isActive(pathname: string, href: string) {
  if (href === "/dashboard") return pathname === "/dashboard";
  return pathname === href || pathname.startsWith(`${href}/`);
}

function withProject(href: string, project: string | null) {
  return project ? `${href}?project=${encodeURIComponent(project)}` : href;
}

/** The dashboard's rail. From the lg breakpoint it can collapse to icons
 * (the shell owns that state); below it, it's a top bar. */
export function Sidebar({
  projects,
  queue,
  collapsed,
  onToggle,
  canSignOut,
}: {
  projects: string[];
  queue: { redisConnected: boolean; queued: number };
  collapsed: boolean;
  onToggle: () => void;
  canSignOut: boolean;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const project = useSearchParams().get("project");
  const [traceId, setTraceId] = useState("");
  // Changing project from a detail page goes to that section's list.
  const section =
    ALL.find((s) => s.href !== "/dashboard" && isActive(pathname, s.href))?.href ?? "/dashboard";
  // Desktop-only class helpers: collapsed hides text, expanded shows it.
  const full = collapsed ? "lg:hidden" : "";
  const footerLink = `flex items-center gap-2.5 rounded px-2 py-1 text-ink-muted hover:bg-surface hover:text-ink ${collapsed ? "lg:justify-center" : ""}`;

  function openTrace(event: FormEvent) {
    event.preventDefault();
    const id = traceId.trim();
    if (id) router.push(`/dashboard/traces/${encodeURIComponent(id)}`);
  }

  return (
    <aside className="border-b border-line-strong bg-rail lg:sticky lg:top-0 lg:z-20 lg:h-screen lg:border-r lg:border-b-0">
      {/* One toggle, on the rail's edge, in the same place open or collapsed. */}
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={!collapsed}
        aria-label={collapsed ? "Expand the sidebar" : "Collapse the sidebar"}
        title={`${collapsed ? "Expand" : "Collapse"} the sidebar  [`}
        className="absolute top-[1.375rem] -right-3 z-10 hidden size-6 place-items-center rounded-full border border-line-strong bg-surface text-ink-muted transition-colors duration-150 hover:border-accent hover:text-accent lg:grid"
      >
        <ChevronLeftIcon
          size={14}
          className={`transition-transform duration-200 ease-out motion-reduce:transition-none ${collapsed ? "rotate-180" : ""}`}
        />
      </button>
      <div className="lg:flex lg:h-full lg:flex-col lg:overflow-x-hidden">
      <div className={`flex items-center justify-between gap-4 px-4 py-3 lg:px-4 lg:pt-5 ${collapsed ? "lg:flex-col lg:px-2" : "lg:block"}`}>
        <Link
          href="/"
          aria-label="TraceroAI home"
          className={`px-1 text-[15px] font-bold tracking-[-0.01em] whitespace-nowrap ${collapsed ? "lg:px-0" : ""}`}
        >
          <span className={full}>TraceroAI</span>
          <span
            aria-hidden="true"
            className={collapsed ? "hidden size-7 place-items-center rounded bg-accent text-[13px] text-white lg:grid" : "hidden"}
          >
            T
          </span>
        </Link>
        {projects.length > 0 && (
          <div className={`lg:mt-5 ${full}`}>
            <label htmlFor="project" className="sr-only lg:not-sr-only lg:mb-1 lg:block lg:px-1 lg:text-xs lg:font-medium lg:text-ink-muted">
              Project
            </label>
            <select
              id="project"
              value={project ?? ""}
              onChange={(event) => router.push(withProject(section, event.target.value || null))}
              className="rounded border border-line-strong bg-surface px-2 py-1.5 text-sm lg:w-full"
            >
              <option value="">All projects</option>
              {projects.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {!collapsed && (
        <form onSubmit={openTrace} className="hidden px-4 lg:block">
          <label htmlFor="trace-id" className="mb-1 block px-1 text-xs font-medium text-ink-muted">
            Open a trace by id
          </label>
          <div className="flex items-center gap-2 rounded border border-line-strong bg-surface px-2 focus-within:outline-2 focus-within:outline-accent">
            <SearchIcon className="shrink-0 text-ink-muted" />
            <input
              id="trace-id"
              value={traceId}
              onChange={(event) => setTraceId(event.target.value)}
              placeholder="Paste a trace id"
              spellCheck={false}
              autoComplete="off"
              className="w-full bg-transparent py-1.5 font-dash-mono text-xs placeholder:font-dash placeholder:text-sm placeholder:text-ink-faint focus:outline-none"
            />
          </div>
        </form>
      )}

      <nav aria-label="Dashboard" className={`flex gap-1 overflow-x-auto px-3 pb-2 lg:mt-5 lg:block lg:space-y-4 ${collapsed ? "lg:px-2" : "lg:px-3"}`}>
        {GROUPS.map((group, gi) => (
          <div key={gi} className="flex gap-1 lg:block lg:space-y-0.5">
            {group.name && (
              <p className={`hidden px-2 pb-1 text-xs font-medium text-ink-muted ${collapsed ? "" : "lg:block"}`}>{group.name}</p>
            )}
            {collapsed && gi > 0 && <hr className="hidden border-line-strong lg:mx-2 lg:mb-2 lg:block" />}
            {group.items.map((item) => {
              const active = isActive(pathname, item.href);
              const ItemIcon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={withProject(item.href, project)}
                  aria-current={active ? "page" : undefined}
                  aria-label={collapsed ? item.label : undefined}
                  title={collapsed ? item.label : undefined}
                  className={`flex items-center gap-2.5 rounded px-2 py-1.5 text-sm whitespace-nowrap ${
                    collapsed ? "lg:justify-center lg:py-2" : ""
                  } ${active ? "bg-accent font-medium text-white" : "text-ink hover:bg-surface"}`}
                >
                  <ItemIcon className={active ? "text-white" : "text-ink-muted"} />
                  <span className={full}>{item.label}</span>
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      <div className={`mt-auto hidden space-y-3 border-t border-line-strong py-4 text-sm lg:block ${collapsed ? "px-2" : "px-4"}`}>
        {!collapsed && (
          <p className="px-1 text-xs leading-5 text-ink-muted">
            {queue.redisConnected
              ? `Judge queue: ${queue.queued === 0 ? "empty" : `${queue.queued} waiting`}`
              : "Judge queue: not connected"}
          </p>
        )}
        <div className="space-y-0.5">
          <Link href="/docs" className={footerLink} aria-label={collapsed ? "Docs" : undefined} title={collapsed ? "Docs" : undefined}>
            <DocsIcon /> <span className={full}>Docs</span>
          </Link>
          <a
            href="https://github.com/chinmai-sd-123/TraceroAI"
            className={footerLink}
            aria-label={collapsed ? "Source on GitHub" : undefined}
            title={collapsed ? "Source on GitHub" : undefined}
          >
            <CodeIcon /> <span className={full}>Source on GitHub</span>
          </a>
          {canSignOut && (
            <form action={logout}>
              <button
                type="submit"
                className={`w-full ${footerLink}`}
                aria-label={collapsed ? "Sign out" : undefined}
                title={collapsed ? "Sign out" : undefined}
              >
                <SignOutIcon /> <span className={full}>Sign out</span>
              </button>
            </form>
          )}
        </div>
      </div>
      </div>
    </aside>
  );
}
