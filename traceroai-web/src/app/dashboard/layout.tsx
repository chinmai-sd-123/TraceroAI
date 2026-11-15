import type { Metadata } from "next";
import { cookies } from "next/headers";

import { getApiStatus, getJobStats, getProjects } from "@/lib/api";
import { dashboardPassword } from "@/lib/dashboard-auth";
import { LAYOUT_COOKIE, parseLayout } from "@/lib/layout-prefs";
import { apiConfigured } from "@/lib/site-mode";

import { ApiStatusBanner } from "./api-status-banner";
import { SelfHostNotice } from "./self-host-notice";
import { DashboardShell } from "./shell";

export const metadata: Metadata = {
  title: "Dashboard",
  robots: { index: false, follow: false },
};

export default async function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // A deployment of just the public pages has no API: explain self-hosting.
  if (!apiConfigured()) return <SelfHostNotice />;

  const [status, projects, queue, cookieStore] = await Promise.all([
    getApiStatus(),
    getProjects(),
    getJobStats(),
    cookies(),
  ]);
  const layout = parseLayout(cookieStore.get(LAYOUT_COOKIE)?.value);

  return (
    <DashboardShell
      initialCollapsed={layout.sidebar === "icons"}
      projects={projects}
      queue={queue}
      canSignOut={Boolean(dashboardPassword())}
      banner={<ApiStatusBanner status={status} />}
    >
      {children}
    </DashboardShell>
  );
}
