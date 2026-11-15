// What the RecoveryAgent can do between attempts. These are the SDK's only two
// levers (sdks/python/traceroai/recovery.py); anything else is shown as a
// plain retry rather than invented.
export const RECOVERY_ACTIONS: Record<string, string> = {
  bump_retrieval: "retrieved more context",
  tighten_generation: "regenerated with a stricter prompt",
};

export function actionWords(action: string | null | undefined): string {
  return (action && RECOVERY_ACTIONS[action]) || "retried";
}
