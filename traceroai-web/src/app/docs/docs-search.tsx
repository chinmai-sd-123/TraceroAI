"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { SearchIcon } from "@/components/icons";
import { docHref } from "@/lib/docs-nav";

type Entry = { slug: string; page: string; heading: string | null; anchor: string | null; text: string };

// Search over a static index of every docs section, fetched once. No service
// behind it, so it works on a self-hosted or offline copy of the docs.

function score(entry: Entry, terms: string[]): number {
  const title = entry.page.toLowerCase();
  const heading = (entry.heading ?? "").toLowerCase();
  const text = entry.text.toLowerCase();
  let total = 0;
  for (const term of terms) {
    const inTitle = title.includes(term);
    const inHeading = heading.includes(term);
    const inText = text.includes(term);
    if (!inTitle && !inHeading && !inText) return 0; // every term must match somewhere
    total += (inTitle ? 6 : 0) + (inHeading ? 4 : 0) + (inText ? 1 : 0);
  }
  return total;
}

function snippet(text: string, terms: string[]): string {
  const lower = text.toLowerCase();
  const at = Math.max(0, Math.min(...terms.map((t) => lower.indexOf(t)).filter((i) => i >= 0)));
  const start = Math.max(0, at - 40);
  return `${start > 0 ? "…" : ""}${text.slice(start, start + 150)}${start + 150 < text.length ? "…" : ""}`;
}

export function DocsSearch() {
  const dialog = useRef<HTMLDialogElement | null>(null);
  const input = useRef<HTMLInputElement | null>(null);
  const router = useRouter();
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);

  const terms = useMemo(
    () => query.toLowerCase().split(/\s+/).filter((t) => t.length > 1),
    [query],
  );
  const results = useMemo(() => {
    if (!entries || terms.length === 0) return [];
    return entries
      .map((entry) => ({ entry, s: score(entry, terms) }))
      .filter((r) => r.s > 0)
      .sort((a, b) => b.s - a.s)
      .slice(0, 8)
      .map((r) => r.entry);
  }, [entries, terms]);

  function open() {
    dialog.current?.showModal();
    input.current?.focus();
    if (!entries && !failed) {
      fetch("/docs/search-index.json")
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
        .then(setEntries)
        .catch(() => setFailed(true));
    }
  }

  function go(entry: Entry) {
    dialog.current?.close();
    setQuery("");
    router.push(`${docHref(entry.slug)}${entry.anchor ? `#${entry.anchor}` : ""}`);
  }

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const typing = target?.closest("input, textarea, select, [contenteditable=true]");
      if ((event.key === "k" && (event.metaKey || event.ctrlKey)) || (event.key === "/" && !typing)) {
        event.preventDefault();
        open();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  return (
    <>
      <button
        type="button"
        onClick={open}
        className="flex w-full items-center gap-2 rounded border border-line-strong bg-surface px-3 py-2 text-left text-sm text-ink-muted hover:border-ink-faint"
      >
        <SearchIcon className="shrink-0" />
        <span className="flex-1">Search the docs</span>
        <kbd className="rounded border border-line px-1.5 font-dash-mono text-xs">/</kbd>
      </button>

      <dialog
        ref={dialog}
        aria-label="Search the docs"
        onClose={() => setActive(0)}
        onClick={(event) => {
          if (event.target === dialog.current) dialog.current?.close(); // click outside the panel
        }}
        className="mx-auto mt-[12vh] w-[min(40rem,calc(100vw-2rem))] rounded border border-line-strong bg-surface p-0 text-ink backdrop:bg-ink/30"
      >
        <div className="flex items-center gap-2 border-b border-line px-4">
          <SearchIcon className="shrink-0 text-ink-muted" />
          <input
            ref={input}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setActive(0);
            }}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown") {
                event.preventDefault();
                setActive((i) => Math.min(i + 1, results.length - 1));
              } else if (event.key === "ArrowUp") {
                event.preventDefault();
                setActive((i) => Math.max(i - 1, 0));
              } else if (event.key === "Enter" && results[active]) {
                go(results[active]);
              }
            }}
            placeholder="Search for a page, setting or error"
            aria-label="Search the docs"
            aria-controls="docs-search-results"
            aria-activedescendant={results[active] ? `docs-result-${active}` : undefined}
            className="w-full bg-transparent py-3.5 text-[15px] placeholder:text-ink-faint focus:outline-none focus-visible:outline-none"
          />
          <kbd className="rounded border border-line px-1.5 font-dash-mono text-xs text-ink-muted">Esc</kbd>
        </div>
        <ul id="docs-search-results" role="listbox" aria-label="Results" className="max-h-[55vh] overflow-y-auto py-2">
          {failed && <li className="px-4 py-3 text-sm text-warn">The search index didn&apos;t load. Use the contents instead.</li>}
          {!failed && terms.length > 0 && entries && results.length === 0 && (
            <li className="px-4 py-3 text-sm text-ink-muted">Nothing matches &ldquo;{query}&rdquo;.</li>
          )}
          {/* Options are chosen with the arrow keys from the input (aria-activedescendant)
              or by clicking; they hold no buttons of their own. */}
          {results.map((entry, i) => (
            <li
              key={`${entry.slug}#${entry.anchor}`}
              id={`docs-result-${i}`}
              role="option"
              aria-selected={i === active}
              onClick={() => go(entry)}
              onMouseEnter={() => setActive(i)}
              className={`cursor-pointer px-4 py-2.5 ${i === active ? "bg-accent-soft" : ""}`}
            >
              <span className="block text-sm font-medium text-ink">
                {entry.page}
                {entry.heading && <span className="font-normal text-ink-muted"> › {entry.heading}</span>}
              </span>
              {entry.text && (
                <span className="mt-0.5 block text-xs leading-5 text-ink-muted">{snippet(entry.text, terms)}</span>
              )}
            </li>
          ))}
        </ul>
      </dialog>
    </>
  );
}
