"use client";

import { useState } from "react";

type Tab = { label: string; code: string };

export function CodeTabs({ tabs }: { tabs: Tab[] }) {
  const [active, setActive] = useState(0);
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(tabs[active].code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked — ignore */
    }
  }

  return (
    <div className="overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950/70">
      <div className="flex items-center justify-between border-b border-zinc-800 bg-zinc-900/60 px-2">
        <div className="flex">
          {tabs.map((tab, i) => (
            <button
              key={tab.label}
              type="button"
              onClick={() => setActive(i)}
              className={`px-4 py-2.5 text-xs font-medium transition ${
                i === active
                  ? "border-b-2 border-cyan-400 text-cyan-200"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={copy}
          className="mr-2 rounded px-2 py-1 text-xs text-zinc-500 transition hover:text-zinc-200"
        >
          {copied ? "Copied ✓" : "Copy"}
        </button>
      </div>
      <pre className="overflow-auto p-5 text-sm leading-6 text-zinc-300">
        <code>{tabs[active].code}</code>
      </pre>
    </div>
  );
}
