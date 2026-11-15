"use client";

import { useRef, type ReactNode } from "react";

/** Tracks the pointer over the hero so the grid can light up around it
 * (the .spotlight layer reads --mx / --my). Mouse only. */
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
  const words = ["Know", "which", "stage", "of", "your", "RAG", "pipeline"];
  return (
    <h1
      id="title"
      className="max-w-[17ch] text-[clamp(2.4rem,5.2vw,4.4rem)] leading-[1.04] font-bold tracking-[-0.035em] text-balance"
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
        failed.
        <svg
          className="title-stroke absolute -bottom-[0.12em] left-[-0.04em] h-[0.32em] w-[105%] overflow-visible"
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
