"use client";

import { useEffect, useRef, useState } from "react";

import { usePrefersReducedMotion } from "./motion";

// The red thread: one thin red line that ties the home page to the single run
// it follows. It starts under the hero's case file, drops to the left gutter,
// runs down the page past a pin at each chapter about that run, and ends at
// the recovery run where the same question was finally answered well.
//
// Anchors are marked in the page with data-thread: "start" (the case file),
// "gutter" (a container whose left edge sets the gutter), "turn" (the hero,
// whose bottom is where the line turns), "pin" (a chapter) and "end".
// Desktop only; under reduced motion the whole line is simply there.

type Geometry = { d: string; height: number; pins: Array<{ x: number; y: number }>; end: { x: number; y: number } };

const R = 18; // corner radius

export function RedThread() {
  const reduced = usePrefersReducedMotion();
  const svg = useRef<SVGSVGElement | null>(null);
  const path = useRef<SVGPathElement | null>(null);
  const [geo, setGeo] = useState<Geometry | null>(null);
  const [reachedY, setReachedY] = useState(0);
  const [tip, setTip] = useState<{ x: number; y: number } | null>(null);

  // Measure the anchors and build the path.
  useEffect(() => {
    const host = svg.current?.parentElement;
    if (!host) return;
    const measure = () => {
      if (window.innerWidth < 1024) return setGeo(null);
      const base = host.getBoundingClientRect();
      const q = (name: string) => host.querySelector<HTMLElement>(`[data-thread="${name}"]`);
      const start = q("start")?.querySelector("article") ?? q("start");
      const gutter = q("gutter");
      const turn = q("turn");
      const end = q("end");
      if (!start || !gutter || !turn || !end) return setGeo(null);
      const s = start.getBoundingClientRect();
      const g = gutter.getBoundingClientRect();
      const t = turn.getBoundingClientRect();
      const e = end.getBoundingClientRect();
      const sx = s.right - 48 - base.left;
      const sy = s.bottom - base.top + 8;
      const gx = g.left - base.left + 14;
      const ty = t.bottom - base.top - 28;
      const ex = e.left - base.left - 6;
      const ey = e.top - base.top + Math.min(e.height / 2, 120);
      const d = [
        `M ${sx} ${sy}`,
        `V ${ty - R}`,
        `Q ${sx} ${ty} ${sx - R} ${ty}`,
        `H ${gx + R}`,
        `Q ${gx} ${ty} ${gx} ${ty + R}`,
        `V ${ey - R}`,
        `Q ${gx} ${ey} ${gx + R} ${ey}`,
        `H ${ex}`,
      ].join(" ");
      const pins = Array.from(host.querySelectorAll<HTMLElement>('[data-thread="pin"]')).map((el) => ({
        x: gx,
        y: el.getBoundingClientRect().top - base.top + 64,
      }));
      setGeo({ d, height: base.height, pins, end: { x: ex, y: ey } });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(host);
    window.addEventListener("resize", measure);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, []);

  // Draw it as far as the reader has scrolled.
  useEffect(() => {
    const el = path.current;
    const host = svg.current?.parentElement;
    if (!geo || !el || !host) return;
    const total = el.getTotalLength();
    el.style.strokeDasharray = `${total}`;
    let frame = 0;
    const update = () => {
      frame = 0;
      const base = host.getBoundingClientRect();
      const target = reduced ? Infinity : window.innerHeight * 0.62 - base.top;
      setReachedY(target);
      // The path only ever moves down, so search for the length at that height.
      let lo = 0;
      let hi = total;
      if (el.getPointAtLength(total).y <= target) lo = total;
      else {
        for (let i = 0; i < 22; i++) {
          const mid = (lo + hi) / 2;
          if (el.getPointAtLength(mid).y <= target) lo = mid;
          else hi = mid;
        }
      }
      el.style.strokeDashoffset = `${total - lo}`;
      // The pen tip, while the line is still being drawn.
      if (lo > 0 && lo < total) {
        const at = el.getPointAtLength(lo);
        setTip({ x: at.x, y: at.y });
      } else setTip(null);
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", onScroll);
    };
  }, [geo, reduced]);

  return (
    <svg
      ref={svg}
      className="red-thread pointer-events-none absolute inset-x-0 top-0 z-[5] w-full max-lg:hidden"
      style={{ height: geo?.height ?? 0 }}
      aria-hidden="true"
    >
      {geo && (
        <>
          <path ref={path} d={geo.d} />
          {geo.pins.map((pin, i) => (
            <circle key={i} cx={pin.x} cy={pin.y} r={4} data-reached={reachedY >= pin.y || undefined} />
          ))}
          <circle cx={geo.end.x} cy={geo.end.y} r={4.5} data-reached={reachedY >= geo.end.y || undefined} />
          {tip && <circle cx={tip.x} cy={tip.y} r={2.5} data-reached />}
        </>
      )}
    </svg>
  );
}
