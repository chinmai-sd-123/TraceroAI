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
    <main className="flex min-h-screen items-center justify-center bg-[#050505] px-4 text-zinc-100">
      <div className="w-full max-w-sm rounded-lg border border-zinc-800 bg-zinc-900/60 p-6">
        <h1 className="text-lg font-semibold">TraceroAI dashboard</h1>
        <p className="mt-1 text-sm text-zinc-500">Enter the dashboard password.</p>
        <LoginForm next={next} />
      </div>
    </main>
  );
}
