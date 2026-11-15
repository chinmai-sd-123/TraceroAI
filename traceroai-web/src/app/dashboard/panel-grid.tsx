"use client";

import { createContext, useContext, useEffect, useState, type DragEvent, type ReactNode } from "react";
import { flushSync } from "react-dom";

import { ArrowLeftIcon, ArrowRightIcon, HideIcon, LayoutIcon, PlusIcon } from "@/components/icons";
import { PANEL_SIZES, type OverviewLayout, type PanelSize } from "@/lib/layout-prefs";

import { saveLayout } from "./layout-store";

// The overview's customizable panels. Each panel has a width (a third, half,
// two thirds or full, of a 12-column grid), a place in the order, and can be
// hidden. "Customize layout" turns on the controls; every change saves to the
// layout cookie, so the server draws the same layout on the next visit.
//
// Rows are always full: panels fill rows in order, and when the next panel
// doesn't fit, the last panel on the row widens to close the gap (it says so
// while editing). Panels on a row share its height. Below the lg breakpoint
// every panel is full width and the controls hide.

export type PanelDef = { id: string; title: string; size: PanelSize };

const SPAN: Record<PanelSize, string> = {
  4: "lg:col-span-4",
  6: "lg:col-span-6",
  8: "lg:col-span-8",
  12: "lg:col-span-12",
};

type Resolved = { order: string[]; sizes: Record<string, PanelSize>; hidden: string[] };

function resolve(defaults: PanelDef[], saved: OverviewLayout | undefined): Resolved {
  const ids = defaults.map((p) => p.id);
  const order = (saved?.order ?? []).filter((id, i, all) => ids.includes(id) && all.indexOf(id) === i);
  // Panels added since the layout was saved go in at their default place.
  ids.forEach((id, i) => {
    if (!order.includes(id)) order.splice(Math.min(i, order.length), 0, id);
  });
  const sizes: Record<string, PanelSize> = {};
  for (const p of defaults) sizes[p.id] = saved?.sizes?.[p.id] ?? p.size;
  const hidden = (saved?.hidden ?? []).filter((id, i, all) => ids.includes(id) && all.indexOf(id) === i);
  return { order, sizes, hidden };
}

/** The width each panel actually gets: rows fill in order, and the last panel
 * on a row that has space left widens to fill it. Sizes are 4, 6, 8 or 12, so
 * the widened width is always one of those too. */
function pack(ids: string[], sizes: Record<string, PanelSize>): Record<string, PanelSize> {
  const spans: Record<string, PanelSize> = {};
  let row: string[] = [];
  let used = 0;
  const close = () => {
    const last = row[row.length - 1];
    if (last) spans[last] = (sizes[last] + 12 - used) as PanelSize;
    row = [];
    used = 0;
  };
  for (const id of ids) {
    if (used + sizes[id] > 12) close();
    row.push(id);
    used += sizes[id];
    spans[id] = sizes[id];
  }
  close();
  return spans;
}

const Editing = createContext<{ editing: boolean; setEditing: (v: boolean) => void } | null>(null);

// Animate a layout change where the browser can (View Transitions), so a panel
// visibly grows, shrinks or moves instead of jumping. Reduced motion: instant.
function animated(update: () => void) {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!document.startViewTransition || reduced) return update();
  document.startViewTransition(() => flushSync(update));
}

/** Holds edit mode so the header button and the grid share it. Esc ends it. */
export function LayoutEditor({ children }: { children: ReactNode }) {
  const [editing, setEditingRaw] = useState(false);
  const setEditing = (value: boolean) => animated(() => setEditingRaw(value));

  useEffect(() => {
    if (!editing) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") animated(() => setEditingRaw(false));
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [editing]);

  return <Editing.Provider value={{ editing, setEditing }}>{children}</Editing.Provider>;
}

function useEditing() {
  const value = useContext(Editing);
  if (!value) throw new Error("Wrap the overview in <LayoutEditor>.");
  return value;
}

export function CustomizeButton() {
  const { editing, setEditing } = useEditing();
  return (
    <button
      type="button"
      onClick={() => setEditing(!editing)}
      aria-pressed={editing}
      className={`hidden h-[2.125rem] items-center gap-2 rounded border px-3 text-sm font-medium transition-colors duration-150 lg:inline-flex ${
        editing
          ? "border-accent bg-accent text-white hover:bg-accent/90"
          : "border-line-strong bg-surface text-ink hover:border-ink-faint"
      }`}
    >
      <LayoutIcon />
      {editing ? "Done" : "Customize layout"}
    </button>
  );
}

export function PanelGrid({
  defaults,
  initial,
  panels,
}: {
  defaults: PanelDef[];
  initial: OverviewLayout | undefined;
  panels: Record<string, ReactNode>; // rendered panels by id; null means nothing to show in this range
}) {
  const { editing } = useEditing();
  const [layout, setLayout] = useState<Resolved>(() => resolve(defaults, initial));
  const [dragging, setDragging] = useState<string | null>(null);
  const [over, setOver] = useState<string | null>(null);
  const titles = Object.fromEntries(defaults.map((p) => [p.id, p.title]));
  const isDefault = JSON.stringify(layout) === JSON.stringify(resolve(defaults, undefined));

  // Only panels with content take part in the layout.
  const visible = layout.order.filter((id) => panels[id] != null && !layout.hidden.includes(id));
  const hidden = layout.hidden.filter((id) => panels[id] != null);
  const spans = pack(visible, layout.sizes);

  function update(next: Resolved) {
    animated(() => setLayout(next));
    saveLayout((p) => ({ ...p, overview: next }));
  }

  function move(id: string, delta: -1 | 1) {
    const swapWith = visible[visible.indexOf(id) + delta];
    if (!swapWith) return;
    const order = [...layout.order];
    const a = order.indexOf(id);
    const b = order.indexOf(swapWith);
    [order[a], order[b]] = [order[b], order[a]];
    update({ ...layout, order });
  }

  // Dropping takes the target's place: moving forward lands after it, moving
  // back lands before it, so every position (first and last too) is reachable.
  function dropOn(target: string) {
    const source = dragging;
    setDragging(null);
    setOver(null);
    if (!source || source === target) return;
    const forward = visible.indexOf(source) < visible.indexOf(target);
    const order = layout.order.filter((id) => id !== source);
    order.splice(order.indexOf(target) + (forward ? 1 : 0), 0, source);
    update({ ...layout, order });
  }

  return (
    <div>
      {editing && (
        <div className="mb-5 hidden flex-wrap items-center gap-x-5 gap-y-2 rounded border border-accent/30 bg-accent-soft px-4 py-2.5 text-sm lg:flex">
          <p className="text-ink">
            Choose each panel&apos;s width, drag the handle or use the arrows to reorder, and hide what you don&apos;t
            need. Changes save in this browser.
          </p>
          {hidden.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-ink-muted">Hidden:</span>
              {hidden.map((id) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => update({ ...layout, hidden: layout.hidden.filter((h) => h !== id) })}
                  className="inline-flex h-7 items-center gap-1.5 rounded border border-line-strong bg-surface px-2 hover:border-accent hover:text-accent"
                >
                  <PlusIcon size={12} />
                  Show {titles[id]}
                </button>
              ))}
            </div>
          )}
          <button
            type="button"
            disabled={isDefault}
            onClick={() => update(resolve(defaults, undefined))}
            className="ml-auto h-7 text-accent hover:underline disabled:cursor-default disabled:text-ink-faint disabled:no-underline"
          >
            Reset layout
          </button>
        </div>
      )}

      {visible.length === 0 ? (
        <p className="rounded border border-dashed border-line-strong px-5 py-10 text-center text-sm text-ink-muted">
          Every panel is hidden. Show one from the bar above, or reset the layout.
        </p>
      ) : (
        <div className="grid gap-6 lg:grid-cols-12">
          {visible.map((id, index) => {
            const size = layout.sizes[id];
            const span = spans[id];
            const target = editing && over === id && dragging && dragging !== id;
            return (
              <div
                key={id}
                style={{ viewTransitionName: `panel-${id}`, viewTransitionClass: "panel" } as React.CSSProperties}
                className={`flex min-w-0 flex-col ${SPAN[span]} ${
                  editing
                    ? "lg:[&>section]:flex-1 lg:[&>section]:rounded-t-none lg:[&>section]:border-accent/30"
                    : "[&>section]:flex-1"
                } ${dragging === id ? "opacity-40" : ""} ${target ? "rounded outline-2 outline-offset-2 outline-accent" : ""}`}
                onDragOver={
                  editing && dragging
                    ? (e: DragEvent) => {
                        e.preventDefault();
                        e.dataTransfer.dropEffect = "move";
                        if (over !== id) setOver(id);
                      }
                    : undefined
                }
                onDragLeave={(e) => {
                  if (!e.currentTarget.contains(e.relatedTarget as Node | null) && over === id) setOver(null);
                }}
                onDrop={editing ? (e) => (e.preventDefault(), dropOn(id)) : undefined}
              >
                {editing && (
                  <div
                    role="group"
                    aria-label={`${titles[id]} layout`}
                    className="hidden h-11 items-center gap-2.5 rounded-t border border-b-0 border-accent/30 bg-accent-soft px-2 lg:flex"
                  >
                    <span
                      draggable
                      onDragStart={(e) => {
                        e.dataTransfer.effectAllowed = "move";
                        e.dataTransfer.setData("text/plain", id);
                        setDragging(id);
                      }}
                      onDragEnd={() => {
                        setDragging(null);
                        setOver(null);
                      }}
                      title="Drag to reorder"
                      aria-hidden="true"
                      className="grid h-7 w-5 cursor-grab place-content-center rounded text-ink-faint hover:bg-surface hover:text-ink-muted active:cursor-grabbing"
                    >
                      <span className="grid grid-cols-2 gap-[3px]">
                        {Array.from({ length: 6 }, (_, i) => (
                          <span key={i} className="size-[3px] rounded-full bg-current" />
                        ))}
                      </span>
                    </span>
                    <div
                      role="radiogroup"
                      aria-label={`${titles[id]} width`}
                      className="flex h-7 rounded border border-line-strong bg-surface p-0.5"
                    >
                      {PANEL_SIZES.map((s) => (
                        <button
                          key={s.value}
                          type="button"
                          role="radio"
                          aria-checked={size === s.value}
                          aria-label={s.name}
                          title={s.name}
                          onClick={() =>
                            size !== s.value && update({ ...layout, sizes: { ...layout.sizes, [id]: s.value } })
                          }
                          className={`min-w-8 rounded-[3px] px-2 text-xs font-medium tabular-nums ${
                            size === s.value ? "bg-accent text-white" : "text-ink-muted hover:bg-sunken hover:text-ink"
                          }`}
                        >
                          {s.label}
                        </button>
                      ))}
                    </div>
                    {span !== size && (
                      <span className="truncate text-xs text-ink-muted" title="The next panel doesn't fit on this row">
                        Widened to fill the row
                      </span>
                    )}
                    <div className="ml-auto flex shrink-0 items-center gap-0.5">
                      <IconButton
                        label={`Move ${titles[id]} earlier`}
                        disabled={index === 0}
                        onClick={() => move(id, -1)}
                      >
                        <ArrowLeftIcon size={14} />
                      </IconButton>
                      <IconButton
                        label={`Move ${titles[id]} later`}
                        disabled={index === visible.length - 1}
                        onClick={() => move(id, 1)}
                      >
                        <ArrowRightIcon size={14} />
                      </IconButton>
                      <IconButton
                        label={`Hide ${titles[id]}`}
                        onClick={() => update({ ...layout, hidden: [...layout.hidden, id] })}
                      >
                        <HideIcon size={14} />
                      </IconButton>
                    </div>
                  </div>
                )}
                {panels[id]}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function IconButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="grid size-7 place-items-center rounded text-ink-muted hover:bg-surface hover:text-ink disabled:pointer-events-none disabled:text-ink-faint/50"
    >
      {children}
    </button>
  );
}
