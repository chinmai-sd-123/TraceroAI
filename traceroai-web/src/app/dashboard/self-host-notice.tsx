import Link from "next/link";

import { CopyButton } from "@/components/copy-button";
import { GITHUB_URL } from "@/components/site/site-chrome";

const COMMAND = `git clone ${GITHUB_URL}.git
cd TraceroAI
docker compose -f infra/docker-compose.yml up --build`;

/** Shown in place of the dashboard on a deployment with no API configured. */
export function SelfHostNotice() {
  return (
    <main className="mx-auto flex min-h-screen max-w-[40rem] flex-col justify-center px-4 py-16 sm:px-8">
      <Link href="/" className="text-[15px] font-bold tracking-[-0.01em]">
        TraceroAI
      </Link>
      <h1 className="mt-8 text-2xl font-semibold tracking-[-0.015em] text-balance">
        The dashboard runs on your own servers
      </h1>
      <p className="mt-3 leading-7 text-ink-muted">
        TraceroAI is self-hosted, so your traces never leave your infrastructure. This site has no API behind it.
        Start the stack and the dashboard opens at <code className="font-dash-mono text-[0.8125rem] text-ink">http://localhost:3000/dashboard</code>.
      </p>
      <div className="mt-6 overflow-hidden rounded bg-[#14202e]">
        <div className="flex items-center justify-between border-b border-white/10 px-4 py-2">
          <span className="text-xs text-white/60">Terminal</span>
          <CopyButton text={COMMAND} label="Copy commands" tone="dark" />
        </div>
        <pre className="overflow-x-auto px-4 py-3 font-dash-mono text-[0.8125rem] leading-6 text-white/90">{COMMAND}</pre>
      </div>
      <p className="mt-4 text-sm leading-6 text-ink-muted">
        Running the stack already and still seeing this? Give the dashboard its API address with{" "}
        <code className="font-dash-mono text-[0.8125rem] text-ink">TRACEROAI_API_URL</code>.
      </p>
      <p className="mt-6 flex flex-wrap gap-x-5 gap-y-2 text-sm">
        <Link href="/docs/self-host/docker-compose" className="text-accent hover:underline">
          Self-hosting guide
        </Link>
        <Link href="/docs/reference/configuration" className="text-accent hover:underline">
          Configuration
        </Link>
        <a href={GITHUB_URL} className="text-accent hover:underline">
          Source on GitHub
        </a>
      </p>
    </main>
  );
}
