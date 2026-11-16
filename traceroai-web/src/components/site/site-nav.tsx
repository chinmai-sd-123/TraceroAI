"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type ComponentType, type ReactNode } from "react";

import {
  ChevronLeftIcon,
  CodeIcon,
  EvalRunsIcon,
  IssuesIcon,
  OverviewIcon,
  RecoveryIcon,
  SearchIcon,
  TracesIcon,
} from "@/components/icons";

import { GITHUB_URL, repoFile } from "@/lib/links";

// The site's top navigation. Each item opens a panel that explains what's
// behind it, on hover (mouse) or click, and by keyboard. It's a disclosure
// (a button and a panel of links), not an ARIA menu: these are links.

type Item = { href: string; title: string; text: string; icon?: ComponentType<{ size?: number }> };
type Panel = { id: string; label: string; width: string; items: Item[]; aside?: "case"; footer?: ReactNode };

const PANELS: Panel[] = [
  {
    id: "product",
    label: "Product",
    width: "46rem",
    aside: "case",
    items: [
      { href: "/#decides", title: "How it decides", text: "Three tiers, and who made each verdict.", icon: OverviewIcon },
      { href: "/#accuracy", title: "Measured accuracy", text: "94–96% for the judge, every verdict published.", icon: EvalRunsIcon },
      { href: "/#diagnose", title: "What it diagnoses", text: "Retrieval misses, unsupported claims, wrong answers.", icon: TracesIcon },
      { href: "/#fix", title: "Issues", text: "Failures with the same cause, grouped into one.", icon: IssuesIcon },
      { href: "/docs/fix/recovery-agent", title: "Recovery agent", text: "Retry the step that failed, and trace each attempt.", icon: RecoveryIcon },
      { href: "/docs/fix/experiments", title: "Experiments", text: "Show a change helps before it ships.", icon: CodeIcon },
    ],
  },
  {
    id: "docs",
    label: "Docs",
    width: "40rem",
    items: [
      { href: "/docs/quickstart", title: "Quickstart", text: "Run the stack and send a first trace." },
      { href: "/docs/first-diagnosis", title: "Your first diagnosis", text: "Read a failed trace, step by step." },
      { href: "/docs/instrument/python-sdk", title: "Python SDK", text: "Trace your pipeline, sync or async." },
      { href: "/docs/self-host/docker-compose", title: "Self-hosting", text: "Docker Compose, then a production checklist." },
      { href: "/docs/reference/http-api", title: "HTTP API", text: "Send traces from any language." },
      { href: "/docs/reference/configuration", title: "Configuration", text: "Every setting, with its default." },
    ],
    footer: (
      <Link href="/docs" className="flex items-center gap-2 text-sm text-ink-muted hover:text-ink">
        <SearchIcon size={14} />
        Search the docs
        <kbd className="ml-auto rounded border border-line px-1.5 font-dash-mono text-xs">/</kbd>
      </Link>
    ),
  },
  {
    id: "open-source",
    label: "Open source",
    width: "30rem",
    items: [
      { href: GITHUB_URL, title: "Source on GitHub", text: "Apache-2.0. Read it, run it, change it." },
      { href: repoFile("CHANGELOG.md"), title: "Changelog", text: "What changed in each release." },
      { href: repoFile("CONTRIBUTING.md"), title: "Contributing", text: "How to propose and land a change." },
      { href: repoFile("SECURITY.md"), title: "Security policy", text: "How to report a vulnerability." },
    ],
    footer: (
      <Link href="/docs/self-host/docker-compose" className="text-sm text-ink-muted hover:text-ink">
        Runs on your servers: Postgres and one Docker Compose command.
      </Link>
    ),
  },
];

export function SiteNav({ current }: { current?: "home" | "docs" }) {
  const [open, setOpen] = useState<string | null>(null);
  const [mobile, setMobile] = useState(false);
  const nav = useRef<HTMLDivElement | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const triggers = useRef<Record<string, HTMLButtonElement | null>>({});
  const [left, setLeft] = useState(0);

  const later = (fn: () => void, ms: number) => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(fn, ms);
  };
  const show = (id: string) => {
    if (timer.current) clearTimeout(timer.current); // a pending close must not win
    const button = triggers.current[id];
    if (button) setLeft(button.offsetLeft - 12);
    setOpen(id);
  };

  // Esc closes and returns focus; a click or focus outside closes.
  useEffect(() => {
    if (!open && !mobile) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (open) triggers.current[open]?.focus();
      setOpen(null);
      setMobile(false);
    };
    const onDown = (event: PointerEvent) => {
      if (!nav.current?.contains(event.target as Node)) {
        setOpen(null);
        setMobile(false);
      }
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onDown);
    };
  }, [open, mobile]);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const panel = PANELS.find((p) => p.id === open);

  return (
    <div
      ref={nav}
      className="contents"
      onBlur={(event) => {
        if (!nav.current?.contains(event.relatedTarget as Node)) setOpen(null);
      }}
    >
      <nav aria-label="Site" className="hidden items-center gap-0.5 text-sm md:flex">
        {PANELS.map((p) => {
          const isOpen = open === p.id;
          const here = p.id === "docs" && current === "docs";
          return (
            <button
              key={p.id}
              ref={(el) => {
                triggers.current[p.id] = el;
              }}
              type="button"
              aria-expanded={isOpen}
              aria-controls={`nav-${p.id}`}
              aria-current={here ? "page" : undefined}
              onClick={() => (isOpen ? setOpen(null) : show(p.id))}
              onPointerEnter={(event) => {
                if (event.pointerType !== "mouse") return;
                // Already open: switch at once. Otherwise wait for intent.
                if (open) show(p.id);
                else later(() => show(p.id), 90);
              }}
              onPointerLeave={(event) => event.pointerType === "mouse" && later(() => setOpen(null), 180)}
              onKeyDown={(event) => {
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  show(p.id);
                  requestAnimationFrame(() => document.querySelector<HTMLElement>(`#nav-${p.id} a`)?.focus());
                }
              }}
              className={`flex items-center gap-1 rounded px-2.5 py-1.5 ${
                isOpen || here ? "bg-sunken text-ink" : "text-ink-muted hover:bg-sunken hover:text-ink"
              }`}
            >
              {p.label}
              <ChevronLeftIcon size={13} className={`transition-transform duration-200 ${isOpen ? "rotate-90" : "-rotate-90"}`} />
            </button>
          );
        })}
      </nav>

      {panel && (
        <div
          id={`nav-${panel.id}`}
          key={panel.id}
          onPointerEnter={(event) => event.pointerType === "mouse" && timer.current && clearTimeout(timer.current)}
          onPointerLeave={(event) => event.pointerType === "mouse" && later(() => setOpen(null), 180)}
          className="nav-panel sheet glass-strong absolute top-[calc(100%-6px)] z-30 hidden overflow-hidden rounded-md border border-line-strong/70 md:block"
          style={{ left, width: `min(${panel.width}, calc(100vw - 2rem))` }}
        >
          <div className={panel.aside ? "grid grid-cols-[minmax(0,1fr)_14.5rem]" : ""}>
            <ul className="grid grid-cols-2 gap-1 p-3">
              {panel.items.map((item) => (
                <li key={item.title}>
                  <NavLink item={item} onPick={() => setOpen(null)} />
                </li>
              ))}
            </ul>
            {panel.aside === "case" && <CaseAside onPick={() => setOpen(null)} />}
          </div>
          {panel.footer && <div className="border-t border-line/80 bg-sunken/60 px-5 py-3">{panel.footer}</div>}
        </div>
      )}

      {/* Phones: one button opens all three groups. */}
      <button
        type="button"
        aria-expanded={mobile}
        aria-controls="nav-mobile"
        onClick={() => setMobile((m) => !m)}
        className="order-last rounded border border-line-strong px-2.5 py-1.5 text-sm font-medium md:hidden"
      >
        {mobile ? "Close" : "Menu"}
      </button>
      {mobile && (
        <div id="nav-mobile" className="glass-strong absolute inset-x-0 top-full z-30 max-h-[calc(100vh-3.5rem)] overflow-y-auto border-b border-line-strong md:hidden">
          {PANELS.map((p) => (
            <section key={p.id} aria-label={p.label} className="border-t border-line px-4 py-4 first:border-t-0">
              <p className="text-xs font-medium text-ink-muted">{p.label}</p>
              <ul className="mt-2 grid gap-1 sm:grid-cols-2">
                {p.items.map((item) => (
                  <li key={item.title}>
                    <NavLink item={item} onPick={() => setMobile(false)} />
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

function NavLink({ item, onPick }: { item: Item; onPick: () => void }) {
  const Icon = item.icon;
  const external = item.href.startsWith("http");
  const body = (
    <>
      {Icon && (
        <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded border border-line bg-surface text-accent group-hover:border-accent/40">
          <Icon size={16} />
        </span>
      )}
      <span className="min-w-0">
        <span className="block text-sm font-semibold text-ink">{item.title}</span>
        <span className="mt-0.5 block text-[13px] leading-5 text-ink-muted">{item.text}</span>
      </span>
    </>
  );
  const className = "group flex gap-3 rounded px-2.5 py-2 hover:bg-sunken focus-visible:bg-sunken";
  return external ? (
    <a href={item.href} className={className} onClick={onPick}>
      {body}
    </a>
  ) : (
    <Link href={item.href} className={className} onClick={onPick}>
      {body}
    </Link>
  );
}

/** The product panel's aside: the one run the home page follows. */
function CaseAside({ onPick }: { onPick: () => void }) {
  return (
    <Link href="/#taken-apart" onClick={onPick} className="group flex flex-col border-l border-line/80 bg-rail/60 p-4 hover:bg-rail">
      <span className="font-dash-mono text-[11px] text-ink-muted">Case 5f7bf901</span>
      <span className="mt-1 text-sm font-semibold">is money within 10 days refunded?</span>
      <span className="mt-3 grid grid-cols-3 gap-1" aria-hidden="true">
        <span className="h-2 bg-pass" />
        <span className="h-2 bg-cause" />
        <span className="h-2 bg-pass" />
      </span>
      <span className="mt-1.5 grid grid-cols-3 gap-1 text-[11px] text-ink-muted" aria-hidden="true">
        <span>Retrieval</span>
        <span className="font-semibold text-cause">Grounding</span>
        <span>Answer</span>
      </span>
      <span className="mt-3 text-[13px] leading-5 text-ink-muted">
        Probable cause: <span className="font-semibold text-cause">unsupported claim</span>, decided by the LLM judge.
      </span>
      <span className="mt-auto pt-4 text-sm font-medium text-accent group-hover:underline">See the run taken apart</span>
    </Link>
  );
}
