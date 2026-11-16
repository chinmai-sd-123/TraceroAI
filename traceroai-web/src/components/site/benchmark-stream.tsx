"use client";

import { useEffect, useRef } from "react";

import { CASE_IDS, EXPECTED, VERDICTS } from "./benchmark-data";
import { usePrefersReducedMotion } from "./motion";

// The benchmark, moving: the same 117 labelled cases in three rows, one per
// evaluation tier, each drawn the way the dashboard draws a diagnosis (three
// stage segments, red at the probable cause, amber where the checks couldn't
// decide; hatched for an estimate, solid for the judge). A wrong diagnosis is
// ringed. The rows drift in alternating directions; the pointer slows them and
// names the case under it. All data is from docs/benchmarks (see
// benchmark-data.ts); nothing here is made up.

const COLORS = { pass: "#1d7348", cause: "#b42318", review: "#95500a", other: "#4f5a6b", ring: "#14202e" };
type Kind = "pass" | "cause" | "review" | "other";

const NAMES: Record<string, string> = {
  H: "Healthy answer",
  C: "Correct refusal",
  R: "Retrieval miss",
  U: "Unsupported claim",
  W: "Wrong answer",
  N: "Needs review",
};
const KINDS: Record<string, [Kind, Kind, Kind]> = {
  H: ["pass", "pass", "pass"],
  C: ["pass", "pass", "pass"],
  R: ["cause", "other", "other"],
  U: ["pass", "cause", "pass"],
  W: ["pass", "pass", "cause"],
  N: ["pass", "review", "pass"],
};

const TIERS = [
  { key: "lexical" as const, name: "Term overlap", short: "Overlap", score: "58%", hatched: true, dir: 1, speed: 10 },
  { key: "embedding" as const, name: "Embeddings", short: "Embeddings", score: "76%", hatched: true, dir: -1, speed: 8 },
  { key: "judge" as const, name: "LLM judge", short: "Judge", score: "94%", hatched: false, dir: 1, speed: 9 },
];

const SEG_W = 9;
const SEG_H = 6;
const GAP = 2;
const GLYPH = SEG_W * 3 + GAP * 2;
const STEP = GLYPH + 15;
const TILE = STEP * CASE_IDS.length;
const ROW_H = 26;

export function BenchmarkStream() {
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const tip = useRef<HTMLDivElement | null>(null);
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const ctx = el.getContext("2d");
    if (!ctx) return;
    let width = 0;
    let frame = 0;
    let pointer: { x: number; y: number } | null = null;
    let speed = 1; // eases toward 0.12 while the pointer is over the band
    let last = performance.now();
    const offsets = TIERS.map((_, i) => i * 977);
    const patterns = new Map<string, CanvasPattern | null>();

    const hatch = (color: string) => {
      if (!patterns.has(color)) {
        const p = document.createElement("canvas");
        p.width = p.height = 4;
        const pc = p.getContext("2d")!;
        pc.strokeStyle = color;
        pc.lineWidth = 1.4;
        pc.beginPath();
        pc.moveTo(0, 4);
        pc.lineTo(4, 0);
        pc.stroke();
        patterns.set(color, ctx.createPattern(p, "repeat"));
      }
      return patterns.get(color)!;
    };

    const resize = () => {
      const ratio = window.devicePixelRatio || 1;
      width = el.clientWidth;
      el.width = Math.round(width * ratio);
      el.height = Math.round(TIERS.length * ROW_H * ratio);
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    };

    const draw = () => {
      ctx.clearRect(0, 0, width, TIERS.length * ROW_H);
      let nearest: { text: string; x: number; y: number; d: number } | null = null;
      TIERS.forEach((tier, r) => {
        const row = VERDICTS[tier.key];
        const y = r * ROW_H + (ROW_H - SEG_H) / 2;
        const shift = ((offsets[r] % TILE) + TILE) % TILE;
        for (let copy = -1; copy * TILE < width + TILE; copy++) {
          for (let i = 0; i < row.length; i++) {
            const x = i * STEP + copy * TILE + (tier.dir > 0 ? shift - TILE : -shift);
            if (x < -GLYPH - 4 || x > width + 4) continue;
            let lift = 0;
            if (pointer) {
              const d = Math.hypot(x + GLYPH / 2 - pointer.x, y + SEG_H / 2 - pointer.y);
              if (d < 64) lift = (1 - d / 64) * 3;
              if (d < 20 && (!nearest || d < nearest.d)) {
                const wrong = row[i] !== EXPECTED[i];
                const name = CASE_IDS[i].replace(/^constructed_/, "").replaceAll("_", " ");
                const said = NAMES[row[i]].toLowerCase();
                nearest = {
                  text: wrong
                    ? `${tier.name} said ${said}; the label is ${NAMES[EXPECTED[i]].toLowerCase()}. Case: ${name}`
                    : `${tier.name} said ${said}, which is right. Case: ${name}`,
                  x,
                  y,
                  d,
                };
              }
            }
            KINDS[row[i]].forEach((kind, s) => {
              ctx.fillStyle = tier.hatched ? hatch(COLORS[kind]) : COLORS[kind];
              ctx.fillRect(x + s * (SEG_W + GAP), y - lift, SEG_W, SEG_H);
            });
            if (row[i] !== EXPECTED[i]) {
              ctx.strokeStyle = COLORS.ring;
              ctx.lineWidth = 1;
              ctx.strokeRect(x - 3.5, y - lift - 3.5, GLYPH + 7, SEG_H + 7);
            }
          }
        }
      });
      const t = tip.current;
      if (!t) return;
      const n = nearest as { text: string; x: number; y: number } | null;
      if (n) {
        t.textContent = n.text;
        t.style.transform = `translate(${Math.min(Math.max(0, width - 360), Math.max(0, n.x - 8))}px, ${n.y - 36}px)`;
        t.style.opacity = "1";
      } else t.style.opacity = "0";
    };

    const tick = (now: number) => {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      speed += ((pointer ? 0.12 : 1) - speed) * Math.min(1, dt * 6);
      TIERS.forEach((tier, i) => (offsets[i] += tier.speed * dt * speed));
      draw();
      frame = requestAnimationFrame(tick);
    };

    resize();
    draw();
    const observer = new IntersectionObserver(([entry]) => {
      cancelAnimationFrame(frame);
      if (entry.isIntersecting && !reduced) {
        last = performance.now();
        frame = requestAnimationFrame(tick);
      }
    });
    observer.observe(el);
    const onResize = () => {
      resize();
      draw();
    };
    const move = (event: PointerEvent) => {
      const box = el.getBoundingClientRect();
      pointer = { x: event.clientX - box.left, y: event.clientY - box.top };
      if (reduced) draw();
    };
    const leave = () => {
      pointer = null;
      draw();
    };
    window.addEventListener("resize", onResize);
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerleave", leave);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("resize", onResize);
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerleave", leave);
    };
  }, [reduced]);

  return (
    <figure aria-labelledby="stream-caption" className="border-y border-line bg-surface py-6">
      <div className="stream-grid grid">
        <ol className="stream-labels border-r border-line pr-4" aria-label="Accuracy by tier">
          {TIERS.map((tier) => (
            <li key={tier.key} className="flex items-center justify-between gap-2 text-xs" style={{ height: ROW_H }}>
              <span className={tier.hatched ? "text-ink-muted" : "font-semibold text-ink"}>
                <span className="max-sm:hidden">{tier.name}</span>
                <span className="sm:hidden">{tier.short}</span>
              </span>
              <span className={`font-dash-mono tabular-nums ${tier.hatched ? "text-ink-muted" : "font-semibold text-ink"}`}>{tier.score}</span>
            </li>
          ))}
        </ol>
        <div className="relative min-w-0">
          <canvas ref={canvas} aria-hidden="true" className="stream-fade block w-full cursor-crosshair opacity-80 transition-opacity duration-300 hover:opacity-100" style={{ height: TIERS.length * ROW_H }} />
          <div
            ref={tip}
            aria-hidden="true"
            className="pointer-events-none absolute top-0 left-0 rounded border border-line-strong bg-surface px-2 py-1 text-xs whitespace-nowrap opacity-0 transition-opacity duration-150"
          />
        </div>
      </div>
      <figcaption id="stream-caption" className="stream-labels mt-4 max-w-[60rem] pr-4 text-xs leading-5 text-ink-muted">
        The 117 labelled cases behind the accuracy figures, as each tier diagnosed them: red where it put the cause, amber
        where it couldn&apos;t decide. Hatched is an estimate, solid is the judge, and a ring is a wrong diagnosis. Point at
        a mark to see its case.
      </figcaption>
    </figure>
  );
}
