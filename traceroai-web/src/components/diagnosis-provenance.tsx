import type { DeepStatus, DiagnosisSource } from "@/lib/trace-types";

// How much to trust a diagnosis, in one sentence: which evaluation produced it,
// and whether the LLM judge is still to come. (The badge form is ProvenanceMark
// in the dashboard's ui.tsx.)

/** One-line explanation for the trace page's diagnosis panel. */
export function provenanceSentence(
  source: DiagnosisSource | undefined,
  status: DeepStatus | undefined,
): string | null {
  if (source === "judge") {
    return status === "partial"
      ? "Diagnosed by the LLM judge, but some of its checks failed; the diagnosis uses the ones that completed."
      : "Diagnosed by the LLM judge.";
  }
  const estimate =
    source === "embedding"
      ? "Estimated from embedding similarity."
      : source === "lexical"
        ? "Estimated from term overlap, which often misses paraphrased answers."
        : null;
  const judge =
    status === "pending"
      ? "The LLM judge hasn't finished yet; reload to see its verdict."
      : status === "failed"
        ? "The LLM judge failed on this trace, so the estimate stands."
        : status === "skipped"
          ? "No LLM judge is configured on this server."
          : null;
  return [estimate, judge].filter(Boolean).join(" ") || null;
}
