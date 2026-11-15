"use client";

import { useEffect } from "react";

/** Keyboard for trace lists. "/" focuses the search box; j and k move down and
 * up the rows. In "focus" mode they move keyboard focus (Enter then opens the
 * row); in "navigate" mode, used beside an open trace, they open the next or
 * previous trace directly. Ignored while typing in a field or with a modifier
 * key held. */
export function ListKeys({ mode = "focus" }: { mode?: "focus" | "navigate" }) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable=true]")) return;

      if (event.key === "/") {
        const search = document.getElementById("trace-search");
        if (search) {
          event.preventDefault();
          search.focus();
        }
        return;
      }
      if (event.key !== "j" && event.key !== "k") return;

      const rows = Array.from(document.querySelectorAll<HTMLAnchorElement>("a[data-list-row]")).filter(
        (row) => row.offsetParent !== null, // skip rows hidden at this width
      );
      if (rows.length === 0) return;
      const step = event.key === "j" ? 1 : -1;
      const current =
        mode === "navigate"
          ? rows.findIndex((row) => row.getAttribute("aria-current") === "page")
          : rows.indexOf(document.activeElement as HTMLAnchorElement);
      const next = rows[Math.min(rows.length - 1, Math.max(0, current === -1 ? 0 : current + step))];
      event.preventDefault();
      if (mode === "navigate") {
        if (next.getAttribute("aria-current") !== "page") next.click();
      } else {
        next.focus();
        next.scrollIntoView({ block: "nearest" });
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [mode]);
  return null;
}
