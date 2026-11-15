"use client";

import { Suspense, useCallback, useEffect, useState, type ReactNode } from "react";

import { saveLayout } from "./layout-store";
import { Sidebar } from "./sidebar";

/** The dashboard frame: the rail (expanded or collapsed to icons) beside the
 * page. The collapsed state starts from the viewer's cookie, so the server
 * renders it right, and toggling saves it back. */
export function DashboardShell({
  initialCollapsed,
  projects,
  queue,
  canSignOut,
  banner,
  children,
}: {
  initialCollapsed: boolean;
  projects: string[];
  queue: { redisConnected: boolean; queued: number };
  canSignOut: boolean;
  banner: ReactNode;
  children: ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(initialCollapsed);

  const toggle = useCallback(() => {
    setCollapsed((was) => {
      const next = !was;
      saveLayout((p) => ({ ...p, sidebar: next ? "icons" : "full" }));
      return next;
    });
  }, []);

  // "[" toggles the sidebar, as in most tools with a collapsible rail.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "[" || event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable=true]")) return;
      if (!window.matchMedia("(min-width: 64rem)").matches) return;
      event.preventDefault();
      toggle();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [toggle]);

  return (
    <div
      className={`min-h-screen lg:grid lg:transition-[grid-template-columns] lg:duration-200 lg:ease-out motion-reduce:transition-none ${collapsed ? "lg:grid-cols-[4rem_minmax(0,1fr)]" : "lg:grid-cols-[14rem_minmax(0,1fr)]"}`}
    >
      {/* The sidebar reads ?project=, which needs a Suspense boundary. */}
      <Suspense fallback={<aside className="border-b border-line-strong bg-rail lg:border-r" />}>
        <Sidebar projects={projects} queue={queue} collapsed={collapsed} onToggle={toggle} canSignOut={canSignOut} />
      </Suspense>
      <main className="min-w-0">
        {banner}
        {children}
      </main>
    </div>
  );
}
