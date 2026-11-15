"use client";

import { useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

import { COLUMNS, clampWidth, type ColumnId } from "@/lib/layout-prefs";

import { saveLayout } from "./layout-store";

/** A drag handle on the edge of a resizable column. The column's width lives
 * in a CSS variable (--col-<id>) on the nearest [data-resize-root], so
 * dragging restyles without re-rendering the page. Keyboard: arrows resize
 * (Shift for bigger steps), Home and End jump to the limits, Enter or a
 * double-click resets. The width is saved when you let go. */
export function Splitter({
  id,
  label,
  initial,
  className = "-right-1.5 lg:block",
}: {
  id: ColumnId;
  label: string;
  initial: number;
  className?: string; // where it sits and from which breakpoint it shows
}) {
  const handle = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(initial);
  const drag = useRef<{ startX: number; startWidth: number } | null>(null);
  const limits = COLUMNS[id];

  function apply(next: number, persist: boolean) {
    const value = clampWidth(id, next);
    handle.current?.closest<HTMLElement>("[data-resize-root]")?.style.setProperty(`--col-${id}`, `${value}px`);
    setWidth(value);
    if (persist) saveLayout((p) => ({ ...p, widths: { ...p.widths, [id]: value } }));
  }

  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { startX: event.clientX, startWidth: width };
    document.body.classList.add("is-resizing");
  }
  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    if (!drag.current) return;
    apply(drag.current.startWidth + (event.clientX - drag.current.startX), false);
  }
  function onPointerUp(event: PointerEvent<HTMLDivElement>) {
    if (!drag.current) return;
    event.currentTarget.releasePointerCapture(event.pointerId);
    drag.current = null;
    document.body.classList.remove("is-resizing");
    apply(width, true);
  }
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const step = event.shiftKey ? 64 : 16;
    const keys: Record<string, number> = {
      ArrowLeft: width - step,
      ArrowRight: width + step,
      Home: limits.min,
      End: limits.max,
      Enter: limits.initial,
    };
    if (event.key in keys) {
      event.preventDefault();
      apply(keys[event.key], true);
    }
  }

  return (
    <div
      ref={handle}
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-valuenow={width}
      aria-valuemin={limits.min}
      aria-valuemax={limits.max}
      tabIndex={0}
      title={`${label}: drag, or use the arrow keys. Double-click to reset.`}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      onDoubleClick={() => apply(limits.initial, true)}
      onKeyDown={onKeyDown}
      className={`group absolute inset-y-0 z-10 hidden w-3 cursor-col-resize touch-none ${className}`}
    >
      <span className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-transparent transition-colors duration-150 group-hover:bg-accent group-focus-visible:bg-accent group-active:bg-accent" />
      <span className="absolute top-1/2 left-1/2 h-8 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full bg-line-strong opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-visible:opacity-100" />
    </div>
  );
}
