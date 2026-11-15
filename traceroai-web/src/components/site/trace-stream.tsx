"use client";

import { useEffect, useRef } from "react";

import { usePrefersReducedMotion } from "./motion";

// A band of traces drifting past, each drawn the way the dashboard draws one:
// three stage segments, red where the probable cause is, amber where the checks
// couldn't decide, hatched where only an estimate has looked. It illustrates
// the notation; it isn't anyone's data.

const COLORS = { pass: "#1d7348", cause: "#b42318", review: "#95500a", other: "#4f5a6b" };
type Kind = keyof typeof COLORS;

const SEG_W = 9;
const SEG_H = 5;
const GAP = 2;
const GLYPH = SEG_W * 3 + GAP * 2;
const SPACING = 15;
const ROWS = 7;
const ROW_H = 17;

function mulberry32(seed: number) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

type Glyph = { x: number; kinds: [Kind, Kind, Kind]; hatched: boolean; gap: boolean };

function makeRow(random: () => number, width: number): Glyph[] {
  const glyphs: Glyph[] = [];
  for (let x = 0; x < width; x += GLYPH + SPACING) {
    const r = random();
    let kinds: Glyph["kinds"] = ["pass", "pass", "pass"];
    if (r > 0.8) kinds = ["cause", "other", "other"];
    else if (r > 0.71) kinds = ["pass", "cause", "pass"];
    else if (r > 0.64) kinds = ["pass", "pass", "cause"];
    else if (r > 0.6) kinds = ["pass", "review", "pass"];
    glyphs.push({ x, kinds, hatched: random() > 0.62, gap: random() > 0.88 });
  }
  return glyphs;
}

function describe(g: Glyph) {
  const [a, b, c] = g.kinds;
  const name =
    a === "cause" ? "Retrieval miss" : b === "cause" ? "Unsupported claim" : c === "cause" ? "Wrong answer" : b === "review" ? "Needs review" : "Healthy answer";
  return `${name} · ${g.hatched ? "estimate only" : "decided by the judge"}`;
}

export function TraceStream() {
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const tip = useRef<HTMLDivElement | null>(null);
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const ctx = el.getContext("2d");
    if (!ctx) return;
    const random = mulberry32(20261114);
    const tile = 1800; // each row repeats every `tile` pixels
    const rows = Array.from({ length: ROWS }, () => makeRow(random, tile));
    const speeds = Array.from({ length: ROWS }, (_, i) => 14 + ((i * 7) % 5) * 6); // px per second
    let width = 0;
    let frame = 0;
    let visible = true;
    let pointer: { x: number; y: number } | null = null;
    let speed = 1; // eases toward 0.15 while the pointer is over the band
    let last = performance.now();
    const offsets = new Array(ROWS).fill(0).map((_, i) => i * 211);
    const patterns = new Map<string, CanvasPattern | null>();

    function hatch(color: string) {
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
        patterns.set(color, ctx!.createPattern(p, "repeat"));
      }
      return patterns.get(color)!;
    }

    function resize() {
      const ratio = window.devicePixelRatio || 1;
      width = el!.clientWidth;
      el!.width = Math.round(width * ratio);
      el!.height = Math.round(ROWS * ROW_H * ratio);
      ctx!.setTransform(ratio, 0, 0, ratio, 0, 0);
    }

    function draw() {
      ctx!.clearRect(0, 0, width, ROWS * ROW_H);
      let nearest: { g: Glyph; x: number; y: number; d: number } | null = null;
      rows.forEach((row, r) => {
        const y = r * ROW_H + (ROW_H - SEG_H) / 2;
        const shift = offsets[r] % tile;
        for (let copy = -1; copy * tile < width + tile; copy++) {
          for (const g of row) {
            if (g.gap) continue;
            const x = g.x + copy * tile - shift;
            if (x < -GLYPH || x > width) continue;
            // Marks near the pointer lift and grow a little.
            let lift = 0;
            let grow = 0;
            if (pointer) {
              const d = Math.hypot(x + GLYPH / 2 - pointer.x, y + SEG_H / 2 - pointer.y);
              if (d < 70) {
                const k = 1 - d / 70;
                lift = k * 3;
                grow = k * 3;
              }
              if (d < 18 && (!nearest || d < nearest.d)) nearest = { g, x, y, d };
            }
            g.kinds.forEach((kind, i) => {
              ctx!.fillStyle = g.hatched ? hatch(COLORS[kind]) : COLORS[kind];
              ctx!.fillRect(x + i * (SEG_W + GAP), y - lift - grow / 2, SEG_W, SEG_H + grow);
            });
          }
        }
      });
      const t = tip.current;
      if (t) {
        const n = nearest as { g: Glyph; x: number; y: number } | null;
        if (n) {
          t.textContent = describe(n.g);
          t.style.transform = `translate(${Math.min(width - 220, Math.max(0, n.x - 8))}px, ${n.y - 34}px)`;
          t.style.opacity = "1";
        } else {
          t.style.opacity = "0";
        }
      }
    }

    function tick(now: number) {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      speed += ((pointer ? 0.15 : 1) - speed) * Math.min(1, dt * 6);
      offsets.forEach((_, i) => (offsets[i] += speeds[i] * dt * speed));
      draw();
      frame = requestAnimationFrame(tick);
    }

    resize();
    draw();
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      cancelAnimationFrame(frame);
      if (visible && !reduced) {
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
    <div className="relative">
      <canvas ref={canvas} aria-hidden="true" className="trace-stream block w-full cursor-crosshair" style={{ height: ROWS * ROW_H }} />
      <div
        ref={tip}
        aria-hidden="true"
        className="pointer-events-none absolute top-0 left-0 rounded border border-line-strong bg-surface px-2 py-1 text-xs whitespace-nowrap opacity-0 transition-opacity duration-150"
      />
    </div>
  );
}
