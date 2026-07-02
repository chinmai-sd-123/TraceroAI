import type { Metadata } from "next";
import Link from "next/link";

import { GitHubLink } from "@/components/github-link";

import { DashboardNav } from "./nav";

export const metadata: Metadata = {
  title: "Dashboard",
  robots: { index: false, follow: false },
};

export default function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <main className="min-h-screen bg-[#050505] text-zinc-100">
      <div className="border-b border-zinc-800">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <Link href="/" className="text-sm font-semibold tracking-wide">
            TraceroAI
          </Link>

          <div className="flex items-center gap-3">
            <DashboardNav />
            <GitHubLink
              label=""
              className="rounded-md p-2 text-zinc-400 transition hover:bg-zinc-900 hover:text-zinc-100"
            />
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-6 py-8">{children}</div>
    </main>
  );
}