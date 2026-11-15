import { SkeletonBlock, SkeletonPage, SkeletonPanel } from "./skeleton";

export default function DashboardLoading() {
  return (
    <SkeletonPage>
      <div className="grid grid-cols-2 rounded border border-line sm:grid-cols-4" aria-hidden="true">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="border-line px-5 py-4 sm:[&:not(:first-child)]:border-l">
            <SkeletonBlock className="h-3.5 w-16" />
            <SkeletonBlock className="mt-2 h-7 w-20" />
            <SkeletonBlock className="mt-3 h-7 w-full" />
          </div>
        ))}
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <SkeletonPanel rows={4} />
        </div>
        <div className="lg:col-span-4">
          <SkeletonPanel rows={4} />
        </div>
      </div>
    </SkeletonPage>
  );
}
