import { SkeletonPage, SkeletonPanel } from "../skeleton";

export default function EvalRunsLoading() {
  return (
    <SkeletonPage>
      <div className="grid gap-6">
        <SkeletonPanel rows={4} />
        <SkeletonPanel rows={3} />
      </div>
    </SkeletonPage>
  );
}
