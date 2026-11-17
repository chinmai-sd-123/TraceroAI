export type StepKind = "agent" | "chain" | "llm" | "tool" | "retriever" | "embedding" | "reranker" | "guardrail";

/** One step inside a run (GET /v1/traces/{id}); steps form a tree through parentId. */
export type TraceStep = {
  stepId: string;
  parentId: string | null;
  kind: StepKind;
  name: string;
  startedAt: string;
  endedAt: string | null;
  durationMs: number | null;
  status: "ok" | "error" | "unset";
  statusMessage: string | null;
  input: unknown;
  output: unknown;
  attributes: Record<string, unknown>;
};

export type TraceDiagnosis =
  | "healthy_answer"
  | "correct_refusal"
  | "retrieval_miss"
  | "unsupported_claim"
  | "wrong_answer"
  | "low_context_relevance"
  | "needs_review"
  | "not_diagnosed";

export type DiagnosisSource = "lexical" | "embedding" | "judge";
export type DeepStatus = "pending" | "complete" | "partial" | "failed" | "skipped";

/** A trace as the dashboard reads it (mapped from the API in lib/api.ts). */
export type Trace = {
  traceId: string;
  timestamp: string;
  status?: string;
  query: {
    original: string;
    rewritten?: string;
  };
  retrieval: {
    strategy: string;
    config?: {
      lexicalTopK?: number;
      denseTopK?: number;
      finalTopK?: number;
      fusion?: string;
      reranker?: string;
    };
    chunks: Array<{
      rank: number;
      chunkId: string;
      documentTitle: string;
      section: string;
      source: string;
      score: number | null; // the retriever's score, when it reported one
      rrfScore?: number;
      lexicalRank?: number;
      denseRank?: number;
      lexicalScore?: number;
      denseScore?: number;
      textPreview: string;
    }>;
  };
  prompt?: {
    version?: string;
    templateName?: string;
    content?: string;
  };
  /** null for a run with no single model answer (an agent run from OpenTelemetry). */
  generation: {
    model: string;
    answer: string;
    provider?: string | null;
    temperature?: number | null;
    parameters?: Record<string, unknown> | null;
    costUsd?: number | null;
    totalTokens?: number | null;
  } | null;
  latency: {
    totalMs: number;
    retrievalMs: number;
    promptBuildMs?: number;
    generationMs: number;
  };
  evaluations: {
    groundedness: {
      label: string;
      score: number;
      reason: string;
    };
    contextRelevance: {
      label: string;
      score: number;
      reason: string;
    };
    answerRelevance: {
      label: string;
      score: number;
      reason: string;
    };
    deepGroundedness?: {
      label: string;
      score: number | null;
      reason: string;
      claims: Array<{ claim: string; supported: boolean; reason: string }>;
    };
    deepContextRelevance?: {
      label: string;
      reason: string;
    };
    deepAnswerRelevance?: {
      label: string;
      reason: string;
    };
  };
  // Which evaluation methods actually ran on this trace. Derived from the
  // evaluator_version of the quick evals + presence of deep (LLM-judge) evals.
  evalMethods?: {
    embedding: boolean; // embedding-based relevance ran
    lexical: boolean; // term-overlap fallback ran
    llmJudge: boolean; // deep LLM-judge evals present
  };
  // Set when this trace is one attempt of a self-healing RecoveryAgent run.
  // `action` is the recovery lever that led to this attempt (absent on attempt 1).
  // `runId` groups the attempts of one run (absent on traces from SDK < 0.5).
  recovery?: { attempt: number; action?: string; runId?: string; topK?: number };
  diagnosis: {
    label: TraceDiagnosis;
    reason: string;
    // Which evaluation produced the label; undefined on traces stored before
    // the API recorded it.
    source?: DiagnosisSource;
  };
  // Where the LLM-judge evaluation stands; undefined on older traces.
  deepStatus?: DeepStatus;
  feedback?: Array<{
    rating: string;
    comment?: string;
    createdAt?: string;
  }>;
  /** Where the trace came from: the SDK or HTTP API, or OpenTelemetry. */
  source: "sdk" | "otlp";
  /** The run's steps, in the order they were sent; only on a single trace. */
  steps: TraceStep[];
};
