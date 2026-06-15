import Link from "next/link";

const navItems = [
  { label: "Overview", href: "/dashboard" },
  { label: "Traces", href: "/dashboard/traces" },
  { label: "Eval Runs", href: "/dashboard/eval-runs" },
];

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

          <nav className="flex items-center gap-1">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="rounded-md px-3 py-2 text-sm text-zinc-400 transition hover:bg-zinc-900 hover:text-zinc-100"
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-6 py-8">{children}</div>
    </main>
  );
}