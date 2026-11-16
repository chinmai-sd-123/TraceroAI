import Link from "next/link";

import { GitHubIcon } from "@/components/github-link";
import { apiConfigured } from "@/lib/site-mode";

export const GITHUB_URL = "https://github.com/chinmai-sd-123/TraceroAI";
export const repoFile = (path: string) => `${GITHUB_URL}/blob/main/${path}`;

/** Top bar for the public pages (home and docs). */
export function SiteHeader({ current }: { current?: "home" | "docs" }) {
  const link = "rounded px-2 py-1 text-ink-muted hover:bg-sunken hover:text-ink";
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-surface/95 backdrop-blur-[2px]">
      <div className="mx-auto flex h-14 max-w-[84rem] items-center gap-6 px-4 sm:px-8">
        <Link href="/" className="text-[15px] font-bold tracking-[-0.01em]" aria-current={current === "home" ? "page" : undefined}>
          TraceroAI
        </Link>
        <nav aria-label="Site" className="hidden items-center gap-1 text-sm md:flex">
          <Link href="/docs" className={link} aria-current={current === "docs" ? "page" : undefined}>
            Docs
          </Link>
          <Link href="/#architecture" className={link}>
            Architecture
          </Link>
          <Link href="/#accuracy" className={link}>
            Accuracy
          </Link>
          <a href={repoFile("CHANGELOG.md")} className={link}>
            Changelog
          </a>
        </nav>
        <div className="ml-auto flex items-center gap-2 text-sm">
          <a
            href={GITHUB_URL}
            className="inline-flex items-center gap-2 rounded border border-line-strong bg-surface px-3 py-1.5 font-medium hover:bg-sunken"
          >
            <GitHubIcon /> <span className="max-sm:sr-only">GitHub</span>
          </a>
          {/* With no API behind this site (public pages only), point at self-hosting. */}
          <Link
            href={apiConfigured() ? "/dashboard" : "/docs/self-host/docker-compose"}
            className="rounded bg-accent px-3 py-1.5 font-medium text-white hover:bg-accent/90"
          >
            {apiConfigured() ? "Open the dashboard" : "Self-host it"}
          </Link>
        </div>
      </div>
    </header>
  );
}

export function SiteFooter() {
  const col = "space-y-2 text-sm";
  const a = "text-ink-muted hover:text-ink hover:underline";
  return (
    <footer className="mt-24 border-t border-line bg-rail">
      <div className="mx-auto grid max-w-[84rem] gap-10 px-4 py-12 sm:px-8 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
        <div>
          <p className="text-[15px] font-bold">TraceroAI</p>
          <p className="mt-2 max-w-sm text-sm text-ink-muted">
            Open-source tracing, evaluation and diagnosis for retrieval-augmented generation. Apache-2.0 licensed.
          </p>
        </div>
        <nav aria-label="Product" className={col}>
          <p className="font-semibold">Product</p>
          <p><Link className={a} href="/docs">Documentation</Link></p>
          <p>
            {apiConfigured() ? (
              <Link className={a} href="/dashboard">Dashboard</Link>
            ) : (
              <Link className={a} href="/docs/self-host/docker-compose">Self-hosting</Link>
            )}
          </p>
          <p><a className={a} href="https://pypi.org/project/traceroai/">Python SDK on PyPI</a></p>
        </nav>
        <nav aria-label="Project" className={col}>
          <p className="font-semibold">Project</p>
          <p><a className={a} href={GITHUB_URL}>Source on GitHub</a></p>
          <p><a className={a} href={repoFile("CHANGELOG.md")}>Changelog</a></p>
          <p><a className={a} href={repoFile("docs/evaluation-benchmark.md")}>Accuracy benchmark</a></p>
        </nav>
        <nav aria-label="Community" className={col}>
          <p className="font-semibold">Community</p>
          <p><a className={a} href={repoFile("CONTRIBUTING.md")}>Contributing</a></p>
          <p><a className={a} href={repoFile("SECURITY.md")}>Security policy</a></p>
          <p><a className={a} href={repoFile("LICENSE")}>Apache-2.0 licence</a></p>
        </nav>
      </div>
      {/* The closing wordmark: navy fading to nothing, cut by the page's edge. */}
      <div className="footer-wordmark-wrap overflow-hidden" aria-hidden="true">
        <p className="footer-wordmark mx-auto max-w-[84rem] px-4 select-none sm:px-8">TraceroAI</p>
      </div>
    </footer>
  );
}
