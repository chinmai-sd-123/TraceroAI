import { SkeletonBlock, SkeletonPanel } from "../skeleton";

export default function TracesLoading() {
  return (
    <section>
      <SkeletonBlock className="h-3 w-20" />
      <SkeletonBlock className="mt-3 h-8 w-64" />
      <SkeletonBlock className="mt-3 h-4 w-full max-w-2xl" />
      <div className="mt-8">
        <SkeletonPanel rows={6} />
      </div>
    </section>
  );
}
