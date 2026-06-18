import { SkeletonBlock, SkeletonPanel } from "../skeleton";

export default function EvalRunsLoading() {
  return (
    <section>
      <SkeletonBlock className="h-3 w-20" />
      <SkeletonBlock className="mt-3 h-8 w-64" />
      <SkeletonBlock className="mt-3 h-4 w-full max-w-2xl" />
      <div className="mt-8 grid gap-6">
        <SkeletonPanel rows={3} />
        <SkeletonPanel rows={3} />
      </div>
    </section>
  );
}
