/** Reusable shimmer blocks for dashboard loading states (Render cold-start can be
 *  slow, so a skeleton beats a blank screen). */

export function SkeletonBlock({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-md bg-zinc-800/60 ${className}`}
      aria-hidden
    />
  );
}

export function SkeletonCard() {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-5">
      <SkeletonBlock className="h-3 w-20" />
      <SkeletonBlock className="mt-3 h-7 w-16" />
    </div>
  );
}

export function SkeletonPanel({ rows = 4 }: { rows?: number }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-6">
      <SkeletonBlock className="h-4 w-32" />
      <div className="mt-5 space-y-3">
        {Array.from({ length: rows }).map((_, i) => (
          <SkeletonBlock key={i} className="h-10 w-full" />
        ))}
      </div>
    </div>
  );
}
