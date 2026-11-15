import { PageFrame } from "./ui";

/** Placeholder blocks for loading states (a cold API can take a while to
 * answer, so a skeleton beats a blank screen). The pulse stops under reduced
 * motion. */

export function SkeletonBlock({ className = "" }: { className?: string }) {
  return <div className={`rounded-[3px] bg-sunken motion-safe:animate-pulse ${className}`} aria-hidden="true" />;
}

export function SkeletonPanel({ rows = 4 }: { rows?: number }) {
  return (
    <div className="rounded border border-line p-5" aria-hidden="true">
      <SkeletonBlock className="h-4 w-32" />
      <div className="mt-5 space-y-3">
        {Array.from({ length: rows }).map((_, i) => (
          <SkeletonBlock key={i} className="h-9 w-full" />
        ))}
      </div>
    </div>
  );
}

/** A page heading and some panels, announced once to screen readers. */
export function SkeletonPage({ children }: { children: React.ReactNode }) {
  return (
    <PageFrame>
      <p role="status" className="sr-only">
        Loading
      </p>
      <div className="border-b border-line pb-5" aria-hidden="true">
        <SkeletonBlock className="h-7 w-48" />
        <SkeletonBlock className="mt-2.5 h-4 w-full max-w-xl" />
      </div>
      <div className="mt-6">{children}</div>
    </PageFrame>
  );
}
