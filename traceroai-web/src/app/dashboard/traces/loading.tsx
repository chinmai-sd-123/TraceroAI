import { SkeletonBlock, SkeletonPage, SkeletonPanel } from "../skeleton";

export default function TracesLoading() {
  return (
    <SkeletonPage>
      <SkeletonBlock className="h-8 w-full max-w-lg" />
      <SkeletonBlock className="mt-3 h-7 w-full max-w-2xl" />
      <div className="mt-5">
        <SkeletonPanel rows={8} />
      </div>
    </SkeletonPage>
  );
}
