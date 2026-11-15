"use client";

import { LAYOUT_COOKIE, parseLayout, type LayoutPrefs } from "@/lib/layout-prefs";

// Browser side of the layout cookie: read the current value, merge a change
// into it, and write it back for a year.

function readCookie(): LayoutPrefs {
  const entry = document.cookie.split("; ").find((c) => c.startsWith(`${LAYOUT_COOKIE}=`));
  return parseLayout(entry?.slice(LAYOUT_COOKIE.length + 1));
}

export function saveLayout(change: (current: LayoutPrefs) => LayoutPrefs) {
  const next = change(readCookie());
  const value = encodeURIComponent(JSON.stringify(next));
  document.cookie = `${LAYOUT_COOKIE}=${value}; path=/; max-age=31536000; SameSite=Lax`;
}
