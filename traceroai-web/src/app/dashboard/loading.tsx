import { SkeletonBlock, SkeletonCard, SkeletonPanel } from "./skeleton";

export default function DashboardLoading() {
  return (
    <section>
      <SkeletonBlock className="h-3 w-24" />
      <SkeletonBlock className="mt-3 h-8 w-72" />
      <SkeletonBlock className="mt-3 h-4 w-full max-w-2xl" />

      <div className="mt-8 grid gap-4 md:grid-cols-3 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_1fr]">
        <SkeletonPanel rows={5} />
        <div className="space-y-6">
          <SkeletonPanel rows={2} />
          <SkeletonPanel rows={4} />
        </div>
      </div>
    </section>
  );
}
