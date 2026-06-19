"use client";

import { useEffect, useState } from "react";

/** Sticky docs sidebar that highlights the section currently in view. */
export function SectionNav({ items }: { items: [string, string][] }) {
  const [active, setActive] = useState(items[0]?.[0] ?? "");

  useEffect(() => {
    const sections = items
      .map(([id]) => document.getElementById(id))
      .filter((el): el is HTMLElement => el !== null);

    // Mark a section active when it crosses the upper part of the viewport.
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActive(entry.target.id);
          }
        }
      },
      { rootMargin: "-10% 0px -70% 0px", threshold: 0 },
    );
    sections.forEach((el) => observer.observe(el));

    // The last section often can't scroll high enough to enter the observer's
    // band, so it would never become active. When the page is scrolled to the
    // bottom, force the last item active.
    const onScroll = () => {
      const atBottom =
        window.innerHeight + window.scrollY >=
        document.documentElement.scrollHeight - 2;
      if (atBottom) {
        const last = items[items.length - 1]?.[0];
        if (last) setActive(last);
      }
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();

    return () => {
      observer.disconnect();
      window.removeEventListener("scroll", onScroll);
    };
  }, [items]);

  return (
    <nav className="sticky top-12 space-y-1 text-sm">
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-cyan-300">
        On this page
      </p>
      {items.map(([id, label]) => {
        const isActive = active === id;
        return (
          <a
            key={id}
            href={`#${id}`}
            className={`block rounded px-2 py-1.5 transition ${
              isActive
                ? "bg-zinc-900 font-medium text-cyan-200"
                : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100"
            }`}
          >
            {label}
          </a>
        );
      })}
    </nav>
  );
}
