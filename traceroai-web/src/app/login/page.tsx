import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { dashboardPassword, safeNextPath } from "@/lib/dashboard-auth";

import { LoginForm } from "./login-form";

export const metadata: Metadata = {
  title: "Sign in",
  robots: { index: false, follow: false },
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const next = safeNextPath((await searchParams).next);
  if (!dashboardPassword()) {
    redirect(next);
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-rail px-4">
      <div className="w-full max-w-sm rounded border border-line-strong bg-surface p-6">
        <p className="text-[15px] font-bold tracking-[-0.01em]">TraceroAI</p>
        <h1 className="mt-4 text-lg font-semibold">Sign in to the dashboard</h1>
        <p className="mt-1 text-sm text-ink-muted">This dashboard is protected by a shared password.</p>
        <LoginForm next={next} />
      </div>
    </main>
  );
}
