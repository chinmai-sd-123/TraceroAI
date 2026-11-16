"use client";

import { useRef, type ReactNode } from "react";

/** Tracks the pointer over the hero so the backdrop can light up around it
 * (the lit layer reads --mx / --my). Mouse only. */
export function Spotlight({ children, className = "" }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement | null>(null);
  return (
    <div
      ref={ref}
      className={className}
      onPointerMove={(event) => {
        if (event.pointerType !== "mouse" || !ref.current) return;
        const box = ref.current.getBoundingClientRect();
        ref.current.style.setProperty("--mx", `${event.clientX - box.left}px`);
        ref.current.style.setProperty("--my", `${event.clientY - box.top}px`);
        ref.current.dataset.lit = "true";
      }}
      onPointerLeave={() => {
        if (ref.current) delete ref.current.dataset.lit;
      }}
    >
      {children}
    </div>
  );
}

/** The headline, its words rising in turn, with a reviewer's red stroke
 * drawn under the last word. Pure CSS: it runs before hydration. */
export function HeroTitle() {
  const words = ["Find", "the", "step", "that"];
  return (
    <h1
      id="title"
      className="max-w-[11ch] text-[clamp(2.75rem,6.4vw,4.75rem)] leading-[0.98] font-bold tracking-[-0.042em] text-balance [margin-left:-0.04em]"
    >
      {/* Spaces sit between the word boxes: inside an inline-block they collapse. */}
      {words.map((word, i) => (
        <span key={word}>
          <span className="title-word" style={{ animationDelay: `${120 + i * 70}ms` }}>
            {word}
          </span>{" "}
        </span>
      ))}
      <span className="title-word relative inline-block whitespace-nowrap" style={{ animationDelay: `${120 + words.length * 70}ms` }}>
        broke.
        <svg
          className="title-stroke absolute -bottom-[0.1em] left-[-0.03em] h-[0.3em] w-[104%] overflow-visible"
          viewBox="0 0 200 20"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path d="M3 14 C 40 6, 85 4, 120 9 S 180 15, 197 6" fill="none" stroke="var(--color-cause)" strokeWidth="4" strokeLinecap="round" />
        </svg>
      </span>
    </h1>
  );
}
