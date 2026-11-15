// The viewer's dashboard layout: sidebar collapsed or not, the widths of the
// resizable columns, and the overview's panel sizes and order. Kept in a cookie
// so the server renders the page at the viewer's sizes from the first frame
// (no jump after load). Per browser; nothing is stored server-side.

export const LAYOUT_COOKIE = "traceroai_layout";

export type PanelSize = 4 | 6 | 8 | 12; // columns of 12: a third, half, two thirds, full
export const PANEL_SIZES: Array<{ value: PanelSize; label: string; name: string }> = [
  { value: 4, label: "⅓", name: "One third" },
  { value: 6, label: "½", name: "Half" },
  { value: 8, label: "⅔", name: "Two thirds" },
  { value: 12, label: "Full", name: "Full width" },
];

export type OverviewLayout = {
  order?: string[];
  sizes?: Record<string, PanelSize>;
  hidden?: string[];
};

export type LayoutPrefs = {
  sidebar?: "full" | "icons";
  widths?: Record<string, number>; // resizable column widths in px, by id
  overview?: OverviewLayout;
};

// The resizable columns: default, minimum and maximum width in px.
export const COLUMNS = {
  traceList: { initial: 304, min: 224, max: 520 },
  timeline: { initial: 336, min: 272, max: 560 },
} as const;
export type ColumnId = keyof typeof COLUMNS;

export function clampWidth(id: ColumnId, value: number | undefined): number {
  const c = COLUMNS[id];
  if (typeof value !== "number" || !Number.isFinite(value)) return c.initial;
  return Math.min(c.max, Math.max(c.min, Math.round(value)));
}

function isSize(value: unknown): value is PanelSize {
  return value === 4 || value === 6 || value === 8 || value === 12;
}

/** Parse the cookie defensively: anything unexpected falls back to defaults. */
export function parseLayout(raw: string | undefined): LayoutPrefs {
  if (!raw) return {};
  try {
    const value = JSON.parse(decodeURIComponent(raw)) as Record<string, unknown>;
    const prefs: LayoutPrefs = {};
    if (value.sidebar === "icons" || value.sidebar === "full") prefs.sidebar = value.sidebar;
    if (value.widths && typeof value.widths === "object") {
      prefs.widths = {};
      for (const [k, v] of Object.entries(value.widths as Record<string, unknown>)) {
        if (k in COLUMNS && typeof v === "number") prefs.widths[k] = clampWidth(k as ColumnId, v);
      }
    }
    const o = value.overview as Record<string, unknown> | undefined;
    if (o && typeof o === "object") {
      prefs.overview = {
        order: Array.isArray(o.order) ? o.order.filter((x): x is string => typeof x === "string").slice(0, 30) : undefined,
        hidden: Array.isArray(o.hidden) ? o.hidden.filter((x): x is string => typeof x === "string").slice(0, 30) : undefined,
        sizes:
          o.sizes && typeof o.sizes === "object"
            ? Object.fromEntries(Object.entries(o.sizes as Record<string, unknown>).filter(([, v]) => isSize(v))) as Record<string, PanelSize>
            : undefined,
      };
    }
    return prefs;
  } catch {
    return {};
  }
}
