"use client";

import { useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";

const REDUCED = "(prefers-reduced-motion: reduce)";

/** True when the visitor asked for reduced motion. */
export function usePrefersReducedMotion() {
  return useSyncExternalStore(
    (onChange) => {
      const query = window.matchMedia(REDUCED);
      query.addEventListener("change", onChange);
      return () => query.removeEventListener("change", onChange);
    },
    () => window.matchMedia(REDUCED).matches,
    () => false,
  );
}

/** Becomes true once the element has scrolled into view, and stays true. */
export function useInView<T extends Element>(threshold = 0.25) {
  const ref = useRef<T | null>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || seen) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setSeen(true);
          observer.disconnect();
        }
      },
      { threshold },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [seen, threshold]);
  return [ref, seen] as const;
}

/** Wipes its content in from the bottom the first time it scrolls into view.
 * The content is visible by default; the wipe only runs once JavaScript has
 * confirmed it's below the fold. */
export function Reveal({ children, className = "" }: { children: ReactNode; className?: string }) {
  const [ref, seen] = useInView<HTMLDivElement>(0.15);
  // "idle" (visible) until mounted; then hidden only if it starts below the fold.
  const [below, setBelow] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (el && el.getBoundingClientRect().top > window.innerHeight) setBelow(true);
  }, [ref]);
  const state = !below ? "idle" : seen ? "shown" : "waiting";
  // The observer watches the outer box and the clip goes on the inner one:
  // Chrome counts an element's own clip-path when measuring how much of it is
  // visible, so a clipped element would never register as seen.
  return (
    <div ref={ref} className={className}>
      <div data-reveal={state} className="reveal">
        {children}
      </div>
    </div>
  );
}

/** Magnifies the image under the pointer, on devices with a fine pointer. */
export function Magnify({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [origin, setOrigin] = useState<string | null>(null);
  return (
    <div
      ref={ref}
      className="magnify overflow-hidden"
      onPointerMove={(event) => {
        if (event.pointerType !== "mouse") return;
        const box = ref.current!.getBoundingClientRect();
        setOrigin(`${((event.clientX - box.left) / box.width) * 100}% ${((event.clientY - box.top) / box.height) * 100}%`);
      }}
      onPointerLeave={() => setOrigin(null)}
      style={{ ["--zoom-origin" as string]: origin ?? "50% 50%" }}
      data-zoomed={origin ? "true" : undefined}
    >
      {children}
    </div>
  );
}
