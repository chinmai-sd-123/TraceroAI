import {
  type ExperimentEvalRun,
  type RegressionEvalRun,
} from "./mock-eval-runs";
import { type MockTrace, type TraceDiagnosis } from "./mock-traces";

type ApiTrace = {
  trace_id: string;
  timestamp: string;
  status?: string | null;
  query: {
    original: string;
    rewritten?: string | null;
  };
  retrieval: {
    strategy: string;
    config?: {
      lexical_top_k?: number | null;
      dense_top_k?: number | null;
      final_top_k?: number | null;
      fusion?: string | null;
      reranker?: string | null;
    } | null;
    chunks: Array<{
      rank: number;
      chunk_id: string;
      document_title?: string | null;
      section?: string | null;
      source?: string | null;
      final_score?: number | null;
      rrf_score?: number | null;
      lexical_rank?: number | null;
      dense_rank?: number | null;
      lexical_score?: number | null;
      dense_score?: number | null;
      text_preview?: string | null;
      text: string;
    }>;
  };
  prompt?: {
    version?: string | null;
    template_name?: string | null;
    content?: string | null;
  } | null;
  generation: {
    model: string;
    answer: string;
    provider?: string | null;
    temperature?: number | null;
    parameters?: Record<string, unknown> | null;
    usage?: {
      prompt_tokens?: number | null;
      completion_tokens?: number | null;
      total_tokens?: number | null;
      cost_usd?: number | null;
    };
  };
  latency: {
    total_ms?: number | null;
    retrieval_ms?: number | null;
    prompt_build_ms?: number | null;
    generation_ms?: number | null;
  };
  evaluations: {
    quick?: Array<{
      evaluator_name: string;
      evaluator_version?: string | null;
      label: string;
      score?: number | null;
      reason?: string | null;
    }>;
    deep?: Array<{
      evaluator_name: string;
      label: string;
      score?: number | null;
      reason?: string | null;
      details?: {
        claims?: Array<{ claim: string; supported: boolean; reason: string }>;
      };
    }>;
  };
  diagnosis: {
    label: TraceDiagnosis | string;
    reason?: string | null;
  };
  feedback?: Array<{
    rating: string;
    comment?: string | null;
    created_at?: string | null;
  }>;
  metadata?: Record<string, unknown> | null;
};
export type ApiEvalRun = {
  eval_run_id: string;
  timestamp: string;
  run_type: "regression" | "experiment";
  status: string;
  dataset: {
    dataset_id: string;
    name: string;
    version?: string | null;
  };
  pipeline: {
    pipeline_version: string;
    retrieval_strategy?: string | null;
    prompt_version?: string | null;
    model?: string | null;
    config?: Record<string, unknown>;
  };
  summary: {
    total_cases: number;
    passed_cases: number;
    failed_cases: number;
    pass_rate?: number | null;
    recommendation?: string | null;
  };
  metrics: Array<{
    metric_name: string;
    score?: number | null;
    threshold?: number | null;
    passed?: boolean | null;
  }>;
  cases: Array<{
    case_id: string;
    question: string;
    expected_answer?: string | null;
    actual_answer?: string | null;
    passed: boolean;
    failure_label?: string | null;
    reason?: string | null;
    trace_id?: string | null;
    scores: Record<string, number>;
    metadata: Record<string, unknown>;
  }>;
  variants: Array<{
    variant_id: string;
    name: string;
    config: Record<string, unknown>;
    passed_cases: number;
    failed_cases: number;
    average_latency_ms?: number | null;
    metrics: Array<{
      metric_name: string;
      score?: number | null;
    }>;
  }>;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_TRACEROAI_API_URL || "http://127.0.0.1:8000";

export async function getTraces(projectId?: string): Promise<MockTrace[]> {
  const url = projectId
    ? `${API_BASE_URL}/v1/traces?project_id=${encodeURIComponent(projectId)}`
    : `${API_BASE_URL}/v1/traces`;
  try {
    const response = await fetch(url, { cache: "no-store" });

    if (!response.ok) {
      return [];
    }

    const traces = (await response.json()) as ApiTrace[];
    return traces.map(mapApiTraceToUiTrace);
  } catch {
    // No fabricated data — an unreachable API shows an honest empty state.
    return [];
  }
}

export type PlaygroundResult = {
  query: string;
  prompt: string;
  answer: string;
  latency_ms: number;
  judged_by: "llm_judge" | "deterministic";
  diagnosis: { label: string; reason: string };
  chunks: Array<{ title: string; score: number; text: string }>;
};

export class PlaygroundError extends Error {
  rateLimited: boolean;
  constructor(message: string, rateLimited = false) {
    super(message);
    this.name = "PlaygroundError";
    this.rateLimited = rateLimited;
  }
}

export async function tryPlayground(question: string): Promise<PlaygroundResult> {
  const response = await fetch(`${API_BASE_URL}/v1/playground`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
    cache: "no-store",
  });
  if (response.status === 429) {
    // Read the server's "slow down" detail; fall back to a sensible default.
    let detail = "You're sending requests too quickly. Please wait a minute and try again.";
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* non-JSON body — keep the default */
    }
    throw new PlaygroundError(detail, true);
  }
  if (!response.ok) {
    throw new PlaygroundError(`Playground request failed (${response.status})`);
  }
  return (await response.json()) as PlaygroundResult;
}

export async function getProjects(): Promise<string[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/v1/traces/projects`, {
      cache: "no-store",
    });
    if (!response.ok) {
      return [];
    }
    return (await response.json()) as string[];
  } catch {
    return [];
  }
}

export async function getEvalRunProjects(): Promise<string[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/v1/eval-runs/projects`, {
      cache: "no-store",
    });
    if (!response.ok) {
      return [];
    }
    return (await response.json()) as string[];
  } catch {
    return [];
  }
}

export type JobStats = {
  redisConnected: boolean;
  queued: number;
};

export async function getJobStats(): Promise<JobStats> {
  try {
    const response = await fetch(`${API_BASE_URL}/v1/jobs/stats`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return { redisConnected: false, queued: 0 };
    }

    const data = (await response.json()) as {
      redis_connected?: boolean;
      queued?: number;
    };
    return {
      redisConnected: Boolean(data.redis_connected),
      queued: data.queued ?? 0,
    };
  } catch {
    return { redisConnected: false, queued: 0 };
  }
}

export async function getTrace(traceId: string): Promise<MockTrace | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/v1/traces/${traceId}`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    const trace = (await response.json()) as ApiTrace;
    return mapApiTraceToUiTrace(trace);
  } catch {
    return null;
  }
}

export async function getEvalRuns(projectId?: string): Promise<{
  regressionRuns: RegressionEvalRun[];
  experimentRuns: ExperimentEvalRun[];
}> {
  const url = projectId
    ? `${API_BASE_URL}/v1/eval-runs?project_id=${encodeURIComponent(projectId)}`
    : `${API_BASE_URL}/v1/eval-runs`;
  try {
    const response = await fetch(url, {
      cache: "no-store",
    });

    if (!response.ok) {
      return { regressionRuns: [], experimentRuns: [] };
    }

    const evalRuns = (await response.json()) as ApiEvalRun[];

    return {
      regressionRuns: evalRuns
        .filter((run) => run.run_type === "regression")
        .map(mapApiEvalRunToRegressionRun),
      experimentRuns: evalRuns
        .filter((run) => run.run_type === "experiment")
        .map(mapApiEvalRunToExperimentRun),
    };
  } catch {
    return { regressionRuns: [], experimentRuns: [] };
  }
}

export async function getEvalRun(evalRunId: string): Promise<ApiEvalRun | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/v1/eval-runs/${evalRunId}`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    return (await response.json()) as ApiEvalRun;
  } catch {
    return null;
  }
}


function mapApiTraceToUiTrace(trace: ApiTrace): MockTrace {
  const groundedness = findEval(trace, "groundedness");
  const contextRelevance = findEval(trace, "context_relevance");
  const answerRelevance = findEval(trace, "answer_relevance");
  const deepGroundedness = trace.evaluations.deep?.find(
    (item) => item.evaluator_name === "claim_groundedness",
  );
  const deepContextRelevance = trace.evaluations.deep?.find(
    (item) => item.evaluator_name === "deep_context_relevance",
  );
  const deepAnswerRelevance = trace.evaluations.deep?.find(
    (item) => item.evaluator_name === "deep_answer_relevance",
  );

  const config = trace.retrieval.config;

  return {
    traceId: trace.trace_id,
    timestamp: trace.timestamp,
    status: trace.status || undefined,
    query: {
      original: trace.query.original,
      rewritten: trace.query.rewritten || undefined,
    },
    retrieval: {
      strategy: trace.retrieval.strategy,
      config: config
        ? {
            lexicalTopK: config.lexical_top_k ?? undefined,
            denseTopK: config.dense_top_k ?? undefined,
            finalTopK: config.final_top_k ?? undefined,
            fusion: config.fusion ?? undefined,
            reranker: config.reranker ?? undefined,
          }
        : undefined,
      chunks: trace.retrieval.chunks.map((chunk) => ({
        rank: chunk.rank,
        chunkId: chunk.chunk_id,
        documentTitle: chunk.document_title || "Untitled document",
        section: chunk.section || "Unknown section",
        source: chunk.source || "unknown",
        score: chunk.final_score ?? 0,
        rrfScore: chunk.rrf_score ?? undefined,
        lexicalRank: chunk.lexical_rank ?? undefined,
        denseRank: chunk.dense_rank ?? undefined,
        lexicalScore: chunk.lexical_score ?? undefined,
        denseScore: chunk.dense_score ?? undefined,
        textPreview: chunk.text_preview || chunk.text,
      })),
    },
    prompt: trace.prompt
      ? {
          version: trace.prompt.version ?? undefined,
          templateName: trace.prompt.template_name ?? undefined,
          content: trace.prompt.content ?? undefined,
        }
      : undefined,
    generation: {
      model: trace.generation.model,
      answer: trace.generation.answer,
      provider: trace.generation.provider ?? null,
      temperature: trace.generation.temperature ?? null,
      parameters: trace.generation.parameters ?? null,
      costUsd: trace.generation.usage?.cost_usd ?? null,
      totalTokens: trace.generation.usage?.total_tokens ?? null,
    },
    latency: {
      totalMs: trace.latency.total_ms ?? 0,
      retrievalMs: trace.latency.retrieval_ms ?? 0,
      promptBuildMs: trace.latency.prompt_build_ms ?? undefined,
      generationMs: trace.latency.generation_ms ?? 0,
    },
    evaluations: {
      groundedness: {
        label: groundedness?.label || "not_evaluated",
        score: groundedness?.score ?? 0,
        reason: groundedness?.reason || "No groundedness result available.",
      },
      contextRelevance: {
        label: contextRelevance?.label || "not_evaluated",
        score: contextRelevance?.score ?? 0,
        reason: contextRelevance?.reason || "No context relevance result available.",
      },
      answerRelevance: {
        label: answerRelevance?.label || "not_evaluated",
        score: answerRelevance?.score ?? 0,
        reason: answerRelevance?.reason || "No answer relevance result available.",
      },
      deepGroundedness: deepGroundedness
        ? {
            label: deepGroundedness.label,
            score: deepGroundedness.score ?? null,
            reason: deepGroundedness.reason || "No reason provided.",
            claims: deepGroundedness.details?.claims ?? [],
          }
        : undefined,
      deepContextRelevance: deepContextRelevance
        ? {
            label: deepContextRelevance.label,
            reason: deepContextRelevance.reason || "No reason provided.",
          }
        : undefined,
      deepAnswerRelevance: deepAnswerRelevance
        ? {
            label: deepAnswerRelevance.label,
            reason: deepAnswerRelevance.reason || "No reason provided.",
          }
        : undefined,
    },
    evalMethods: {
      // "Embedding" vs "Lexical" describe which path the RELEVANCE scorers took:
      // they prefer embeddings and fall back to term-overlap only when embeddings
      // are unavailable. Groundedness is excluded here because it is always
      // deterministic by design (claim/term based, no embedding path) — counting
      // it would peg "Lexical (fallback)" near 100% on every trace and wrongly
      // imply the fallback fired. So we derive these flags from the relevance
      // evaluators, which actually have both paths.
      embedding: (trace.evaluations.quick ?? []).some(
        (e) => isRelevanceEval(e) && e.evaluator_version?.startsWith("embedding"),
      ),
      lexical: (trace.evaluations.quick ?? []).some(
        (e) => isRelevanceEval(e) && e.evaluator_version?.startsWith("deterministic"),
      ),
      llmJudge: (trace.evaluations.deep ?? []).length > 0,
    },
    // A RecoveryAgent attempt tags itself via metadata {agent:"recovery", attempt:N}.
    recovery:
      trace.metadata?.agent === "recovery"
        ? {
            attempt: Number(trace.metadata?.attempt) || 1,
            action:
              typeof trace.metadata?.recovery_action === "string"
                ? trace.metadata.recovery_action
                : undefined,
          }
        : undefined,
    diagnosis: {
      label: normalizeDiagnosis(trace.diagnosis.label),
      reason: trace.diagnosis.reason || "No diagnosis available.",
    },
    feedback: (trace.feedback ?? []).map((item) => ({
      rating: item.rating,
      comment: item.comment ?? undefined,
      createdAt: item.created_at ?? undefined,
    })),
  };
}

function findEval(trace: ApiTrace, evaluatorName: string) {
  return trace.evaluations.quick?.find(
    (item) => item.evaluator_name === evaluatorName,
  );
}

// The relevance scorers (context + answer) are the only quick evaluators with
// BOTH an embedding path and a lexical fallback. Groundedness is always
// deterministic by design, so it is excluded from the embedding/lexical mix.
const RELEVANCE_EVALUATORS = new Set([
  "context_relevance",
  "answer_relevance",
]);

function isRelevanceEval(e: { evaluator_name: string }) {
  return RELEVANCE_EVALUATORS.has(e.evaluator_name);
}

function normalizeDiagnosis(label: string): TraceDiagnosis {
  const knownLabels: TraceDiagnosis[] = [
    "healthy_answer",
    "correct_refusal",
    "retrieval_miss",
    "unsupported_claim",
    "wrong_answer",
    "low_context_relevance",
    "needs_review",
  ];

  if (knownLabels.includes(label as TraceDiagnosis)) {
    return label as TraceDiagnosis;
  }

  return "needs_review";
}

function mapApiEvalRunToRegressionRun(run: ApiEvalRun): RegressionEvalRun {
  const groundedness = findMetric(run, "groundedness");
  const retrievalRelevance = findMetric(run, "retrieval_relevance");
  const answerRelevance = findMetric(run, "answer_relevance");

  return {
    id: run.eval_run_id,
    type: "regression",
    timestamp: run.timestamp,
    pipelineVersion: run.pipeline.pipeline_version,
    datasetName: run.dataset.name,
    summary: {
      totalCases: run.summary.total_cases,
      passedCases: run.summary.passed_cases,
      failedCases: run.summary.failed_cases,
      overallAccuracy: toPercent(run.summary.pass_rate),
      statusAccuracy: toPercent(answerRelevance?.score),
      retrievalAccuracy: toPercent(retrievalRelevance?.score),
      failureLabelAccuracy: toPercent(groundedness?.score),
    },
  };
}

function mapApiEvalRunToExperimentRun(run: ApiEvalRun): ExperimentEvalRun {
  // Variants can differ in several dimensions at once (top_k AND prompt AND model),
  // so we identify each by its descriptive name rather than a single config value —
  // this keeps row labels unique and human-readable.
  const values = run.variants.map((variant) => ({
    value: variant.name || variant.variant_id,
    healthyRate: toPercent(
      safeDivide(variant.passed_cases, variant.passed_cases + variant.failed_cases),
    ),
    sourceRecallRate: toPercent(findMetricOnVariant(variant, "source_recall")?.score),
    contextPrecision: toPercent(
      findMetricOnVariant(variant, "context_precision")?.score,
    ),
    avgLatencyMs: variant.average_latency_ms ?? 0,
  }));

  // Winner = highest accuracy (tie-break: lower latency). Computed here, not parsed
  // from the recommendation sentence, so the badge is always correct.
  const winner = [...values].sort(
    (a, b) => b.healthyRate - a.healthyRate || a.avgLatencyMs - b.avgLatencyMs,
  )[0];

  return {
    id: run.eval_run_id,
    type: "experiment",
    timestamp: run.timestamp,
    experimentName: run.pipeline.pipeline_version,
    comparedParameter: "Variant",
    values,
    recommendation: {
      value: winner?.value ?? "review",
      reason:
        run.summary.recommendation ||
        "Review the experiment variants and choose the best quality-latency tradeoff.",
    },
  };
}

function findMetric(run: ApiEvalRun, metricName: string) {
  return run.metrics.find((metric) => metric.metric_name === metricName);
}

function findMetricOnVariant(
  variant: ApiEvalRun["variants"][number],
  metricName: string,
) {
  return variant.metrics.find((metric) => metric.metric_name === metricName);
}


function toPercent(score: number | null | undefined) {
  if (score == null) {
    return 0;
  }

  return Math.round(score * 100);
}

function safeDivide(numerator: number, denominator: number) {
  if (denominator === 0) {
    return 0;
  }

  return numerator / denominator;
}
