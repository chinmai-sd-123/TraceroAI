import type { DeepStatus, DiagnosisSource } from "@/lib/mock-traces";

// How much to trust a diagnosis: which evaluation produced it, and whether the
// LLM judge is still to come.

const SOURCE_LABELS: Record<DiagnosisSource, string> = {
  judge: "LLM judge",
  embedding: "Embedding estimate",
  lexical: "Lexical estimate",
};

export function sourceLabel(source: DiagnosisSource | undefined): string | null {
  return source ? SOURCE_LABELS[source] : null;
}

export function deepStatusNote(status: DeepStatus | undefined): string | null {
  switch (status) {
    case "pending":
      return "Judge pending";
    case "failed":
      return "Judge failed";
    case "skipped":
      return "No judge configured";
    default:
      return null;
  }
}

/** One-line explanation for the trace page's diagnosis panel. */
export function provenanceSentence(
  source: DiagnosisSource | undefined,
  status: DeepStatus | undefined,
): string | null {
  if (source === "judge") return "Diagnosed by the LLM judge.";
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

export function ProvenanceBadge({
  source,
  status,
  size = "md",
}: {
  source: DiagnosisSource | undefined;
  status: DeepStatus | undefined;
  size?: "sm" | "md";
}) {
  const label = sourceLabel(source);
  const note = source === "judge" ? null : deepStatusNote(status);
  if (!label && !note) return null;

  const judged = source === "judge";
  const padding = size === "sm" ? "px-1.5 py-0.5 text-[11px]" : "px-3 py-2 text-sm";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border font-medium ${padding} ${
        judged
          ? "border-violet-500/30 bg-violet-500/10 text-violet-300"
          : "border-zinc-700 bg-zinc-900 text-zinc-400"
      }`}
    >
      {label}
      {label && note ? <span aria-hidden="true">·</span> : null}
      {note}
    </span>
  );
}
