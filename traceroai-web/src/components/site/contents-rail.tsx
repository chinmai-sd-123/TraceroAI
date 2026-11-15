"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";

export type ContentsItem = { id: string; label: string };

/** The report's table of contents. A highlight glides to the section being
 * read (the last one whose heading has passed the top quarter of the window);
 * sections already passed are marked solid. */
export function ContentsRail({ items, label = "Contents" }: { items: ContentsItem[]; label?: string }) {
  const [current, setCurrent] = useState(0);
  const list = useRef<HTMLOListElement | null>(null);
  const [marker, setMarker] = useState<{ top: number; height: number } | null>(null);

  useEffect(() => {
    const sections = items.map((item) => document.getElementById(item.id));
    function update() {
      const line = window.innerHeight * 0.25;
      let active = 0;
      sections.forEach((section, i) => {
        if (section && section.getBoundingClientRect().top <= line) active = i;
      });
      // At the very bottom the last section wins even if its heading is low.
      if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2) active = items.length - 1;
      setCurrent(active);
    }
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, [items]);

  // Measure the active link (relative to the list, its offset parent) so the
  // highlight can glide to it.
  useLayoutEffect(() => {
    const link = list.current?.querySelectorAll<HTMLAnchorElement>("a")[current];
    if (link) setMarker({ top: link.offsetTop, height: link.offsetHeight });
  }, [current]);

  return (
    <nav aria-label={label}>
      <p className="mb-3 pl-3 text-xs font-semibold text-ink-muted">{label}</p>
      <ol ref={list} className="relative text-sm">
        {marker && (
          <span
            aria-hidden="true"
            className="absolute inset-x-0 rounded-[3px] bg-accent-soft transition-[top,height] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]"
            style={{ top: marker.top, height: marker.height }}
          >
            <span className="absolute inset-y-1 left-0 w-0.5 rounded-full bg-accent" />
          </span>
        )}
        {items.map((item, i) => {
          const on = i === current;
          const passed = i < current;
          return (
            <li key={item.id}>
              <a
                href={`#${item.id}`}
                aria-current={on ? "location" : undefined}
                className={`group relative z-[1] flex items-center gap-2.5 py-1.5 pr-2 pl-3 transition-colors duration-200 ${
                  on ? "font-semibold text-ink" : "text-ink-muted hover:text-ink"
                }`}
              >
                <span
                  aria-hidden="true"
                  className={`relative size-2 shrink-0 rounded-full border transition-all duration-300 ${
                    on
                      ? "border-accent bg-accent ring-[3px] ring-accent/20"
                      : passed
                        ? "border-accent bg-accent/70"
                        : "border-line-strong bg-surface group-hover:border-ink-muted"
                  }`}
                />
                <span className="transition-transform duration-200 ease-out group-hover:translate-x-0.5">{item.label}</span>
              </a>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
