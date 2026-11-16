import {
  type ExperimentEvalRun,
  type RegressionEvalRun,
} from "./eval-run-types";
import {
  type DeepStatus,
  type DiagnosisSource,
  type Trace,
  type TraceDiagnosis,
} from "./trace-types";

const DIAGNOSIS_SOURCES: readonly DiagnosisSource[] = ["lexical", "embedding", "judge"];
const DEEP_STATUSES: readonly DeepStatus[] = ["pending", "complete", "partial", "failed", "skipped"];

// A known value from the API, or undefined (older traces, or a value this build
// doesn't know yet).
function oneOf<T extends string>(value: string | null | undefined, known: readonly T[]) {
  return known.includes(value as T) ? (value as T) : undefined;
}

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
    deep_status?: string | null;
  };
  diagnosis: {
    label: TraceDiagnosis | string;
    reason?: string | null;
    source?: string | null;
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
    variant_id?: string | null; // set on experiment cases
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

// Server rendering may reach the API on an internal address the browser can't
// (http://api:8000 in Docker Compose), so the server prefers TRACEROAI_API_URL.
// That variable is never sent to the browser; browser code uses the public URL.
const API_BASE_URL =
  (typeof window === "undefined" ? process.env.TRACEROAI_API_URL : undefined) ||
  process.env.NEXT_PUBLIC_TRACEROAI_API_URL ||
  "http://127.0.0.1:8000";

// The dashboard reads the API with TRACEROAI_API_KEY, from the server only: the
// variable isn't NEXT_PUBLIC_, so Next.js never puts it in browser code. Use an
// admin key to see every project, or a project key to show just one.
function serverHeaders(): Record<string, string> {
  const key =
    typeof window === "undefined" ? process.env.TRACEROAI_API_KEY : undefined;
  return key ? { Authorization: `Bearer ${key}` } : {};
}

export type ApiStatus = "ok" | "unreachable" | "unauthorized" | "degraded";

/**
 * Whether the dashboard can trust what it shows. Every data fetcher falls back
 * to an empty result on failure, so without this an unreachable API, a wrong
 * key and an empty project all look the same.
 */
export async function getApiStatus(): Promise<ApiStatus> {
  try {
    const ready = await fetch(`${API_BASE_URL}/health/ready`, { cache: "no-store" });
    if (ready.status === 503) return "degraded";
    const probe = await fetch(`${API_BASE_URL}/v1/traces?limit=1`, {
      cache: "no-store",
      headers: serverHeaders(),
    });
    if (probe.status === 401 || probe.status === 403) return "unauthorized";
    return probe.ok ? "ok" : "degraded";
  } catch {
    return "unreachable";
  }
}

export type FeedbackRating = "thumbs_up" | "thumbs_down";

/** Server-side: record feedback on a trace with the dashboard's key. */
export async function postFeedback(
  traceId: string,
  rating: FeedbackRating,
  comment: string | null,
): Promise<{ ok: true } | { ok: false; status: number }> {
  try {
    const response = await fetch(
      `${API_BASE_URL}/v1/traces/${encodeURIComponent(traceId)}/feedback`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", ...serverHeaders() },
        body: JSON.stringify({ rating, comment }),
        cache: "no-store",
      },
    );
    return response.ok ? { ok: true } : { ok: false, status: response.status };
  } catch {
    return { ok: false, status: 0 };
  }
}

export type TraceQuery = {
  projectId?: string;
  limit?: number;
  cursor?: string;
  diagnosis?: string;
  q?: string;
  since?: string;
  model?: string;
  environment?: string;
  recoveryRunId?: string;
  issueKey?: string;
  sort?: TraceSort;
};

export type TraceSort = "newest" | "oldest" | "slowest";

export type TracePage = { traces: Trace[]; nextCursor: string | null };

/** One page of traces, filtered and sorted on the server (newest first by default). */
export async function getTraces(query: TraceQuery = {}): Promise<TracePage> {
  const params = new URLSearchParams();
  if (query.projectId) params.set("project_id", query.projectId);
  if (query.limit) params.set("limit", String(query.limit));
  if (query.cursor) params.set("cursor", query.cursor);
  if (query.diagnosis) params.set("diagnosis", query.diagnosis);
  if (query.q) params.set("q", query.q);
  if (query.since) params.set("since", query.since);
  if (query.model) params.set("model", query.model);
  if (query.environment) params.set("environment", query.environment);
  if (query.recoveryRunId) params.set("recovery_run_id", query.recoveryRunId);
  if (query.issueKey) params.set("issue_key", query.issueKey);
  if (query.sort && query.sort !== "newest") params.set("sort", query.sort);
  try {
    const response = await fetch(`${API_BASE_URL}/v1/traces?${params}`, {
      cache: "no-store",
      headers: serverHeaders(),
    });

    if (!response.ok) {
      return { traces: [], nextCursor: null };
    }

    const traces = (await response.json()) as ApiTrace[];
    return {
      traces: traces.map(mapApiTraceToUiTrace),
      nextCursor: response.headers.get("X-Next-Cursor"),
    };
  } catch {
    // No fabricated data — an unreachable API shows an honest empty state.
    return { traces: [], nextCursor: null };
  }
}

export type TraceSummary = {
  total: number;
  healthy: number;
  byDiagnosis: Record<string, number>;
  bySource: Record<string, number>;
  byModel: Record<string, number>;
  byEnvironment: Record<string, number>;
  latencyMs: { measured: number; avg: number | null; p50: number | null; p95: number | null };
  costUsd: { priced: number; total: number | null; avg: number | null };
};

/** The time ranges the dashboard offers. "all" has no lower bound. */
export const TIME_RANGES = {
  "24h": { label: "Last 24 hours", hours: 24 },
  "7d": { label: "Last 7 days", hours: 24 * 7 },
  "30d": { label: "Last 30 days", hours: 24 * 30 },
  all: { label: "All time", hours: null },
} as const;
export type TimeRange = keyof typeof TIME_RANGES;

export function parseRange(value: string | undefined, fallback: TimeRange = "7d"): TimeRange {
  return value && value in TIME_RANGES ? (value as TimeRange) : fallback;
}

/** ISO start of a range, or undefined for "all". */
export function rangeSince(range: TimeRange): string | undefined {
  const hours = TIME_RANGES[range].hours;
  return hours === null ? undefined : new Date(Date.now() - hours * 3_600_000).toISOString();
}

export type TimeBucket = { start: string; total: number; healthy: number; p95Ms: number | null };

/** Traces, healthy traces and p95 latency per hour (24h) or day (longer). */
export async function getTimeseries(
  projectId: string | undefined,
  range: TimeRange,
): Promise<{ bucket: "hour" | "day"; buckets: TimeBucket[] } | null> {
  const params = new URLSearchParams();
  if (projectId) params.set("project_id", projectId);
  // "All time" charts the last 90 days by day; older history isn't useful as a trend.
  const since = rangeSince(range) ?? new Date(Date.now() - 90 * 86_400_000).toISOString();
  params.set("since", since);
  try {
    const response = await fetch(`${API_BASE_URL}/v1/metrics/timeseries?${params}`, {
      cache: "no-store",
      headers: serverHeaders(),
    });
    if (!response.ok) return null;
    const data = (await response.json()) as {
      bucket: "hour" | "day";
      buckets: Array<{ start: string; total: number; healthy: number; p95_ms: number | null }>;
    };
    return {
      bucket: data.bucket,
      buckets: data.buckets.map((b) => ({
        start: b.start,
        total: b.total,
        healthy: b.healthy,
        p95Ms: b.p95_ms,
      })),
    };
  } catch {
    return null;
  }
}

export type RecoveryRun = {
  runId: string;
  question: string;
  attempts: number;
  traceIds: string[];
  diagnoses: Array<string | null>; // one per attempt, in order
  firstDiagnosis: string | null;
  finalDiagnosis: string | null;
  actions: Array<string | null>; // the lever pulled before each attempt (null on the first)
  topK: Array<number | null>;
  startedAt: string;
  endedAt: string;
};

/** RecoveryAgent runs, most recently active first, grouped by the API. */
export async function getRecoveryRuns(
  projectId: string | undefined,
  options: { range?: TimeRange; limit?: number } = {},
): Promise<RecoveryRun[] | null> {
  const params = new URLSearchParams();
  if (projectId) params.set("project_id", projectId);
  const since = options.range ? rangeSince(options.range) : undefined;
  if (since) params.set("since", since);
  params.set("limit", String(options.limit ?? 50));
  try {
    const response = await fetch(`${API_BASE_URL}/v1/recovery-runs?${params}`, {
      cache: "no-store",
      headers: serverHeaders(),
    });
    if (!response.ok) return null;
    const runs = (await response.json()) as Array<{
      run_id: string;
      question: string;
      attempts: number;
      trace_ids: string[];
      diagnoses: Array<string | null>;
      first_diagnosis: string | null;
      final_diagnosis: string | null;
      actions: Array<string | null>;
      top_k: Array<number | null>;
      started_at: string;
      ended_at: string;
    }>;
    return runs.map((r) => ({
      runId: r.run_id,
      question: r.question,
      attempts: r.attempts,
      traceIds: r.trace_ids,
      diagnoses: r.diagnoses,
      firstDiagnosis: r.first_diagnosis,
      finalDiagnosis: r.final_diagnosis,
      actions: r.actions,
      topK: r.top_k,
      startedAt: r.started_at,
      endedAt: r.ended_at,
    }));
  } catch {
    return null;
  }
}

/** Headline numbers over every trace in scope, computed by the API in SQL. */
export type IssueStatus = "open" | "regressed" | "resolved";

/** Failing traces that share a cause: a failure label and the source of the top chunk. */
export type Issue = {
  projectId: string;
  issueKey: string;
  label: string;
  source: string; // the top retrieved source, or the prompt version (see groupedBy)
  groupedBy: "top_source" | "prompt_version";
  status: IssueStatus;
  count: number;
  questions: number;
  firstSeen: string;
  lastSeen: string;
  resolvedAt: string | null;
  countSinceResolved: number;
  latestTraceId: string;
  recentQuestions: string[];
};

/** Issues with failures in the range: regressed first, then open, then resolved. Null if the API failed. */
export async function getIssues(
  projectId: string | undefined,
  options: { range?: TimeRange; status?: IssueStatus; limit?: number } = {},
): Promise<Issue[] | null> {
  const params = new URLSearchParams();
  if (projectId) params.set("project_id", projectId);
  const since = options.range ? rangeSince(options.range) : undefined;
  if (since) params.set("since", since);
  if (options.status) params.set("status", options.status);
  params.set("limit", String(options.limit ?? 100));
  try {
    const response = await fetch(`${API_BASE_URL}/v1/issues?${params}`, { cache: "no-store", headers: serverHeaders() });
    if (!response.ok) return null;
    const issues = (await response.json()) as Array<{
      project_id: string;
      issue_key: string;
      label: string;
      source: string;
      grouped_by: "top_source" | "prompt_version";
      status: IssueStatus;
      count: number;
      questions: number;
      first_seen: string;
      last_seen: string;
      resolved_at: string | null;
      count_since_resolved: number;
      latest_trace_id: string;
      recent_questions: string[];
    }>;
    return issues.map((i) => ({
      projectId: i.project_id,
      issueKey: i.issue_key,
      label: i.label,
      source: i.source,
      groupedBy: i.grouped_by,
      status: i.status,
      count: i.count,
      questions: i.questions,
      firstSeen: i.first_seen,
      lastSeen: i.last_seen,
      resolvedAt: i.resolved_at,
      countSinceResolved: i.count_since_resolved,
      latestTraceId: i.latest_trace_id,
      recentQuestions: i.recent_questions,
    }));
  } catch {
    return null;
  }
}

/** Server-side: mark an issue resolved, or open again, with the dashboard's key. */
export async function setIssueResolved(
  projectId: string,
  issueKey: string,
  resolved: boolean,
): Promise<{ ok: true } | { ok: false; status: number }> {
  try {
    const response = await fetch(`${API_BASE_URL}/v1/issues/${resolved ? "resolve" : "reopen"}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...serverHeaders() },
      body: JSON.stringify({ project_id: projectId, issue_key: issueKey }),
      cache: "no-store",
    });
    return response.ok ? { ok: true } : { ok: false, status: response.status };
  } catch {
    return { ok: false, status: 0 };
  }
}

export async function getSummary(
  projectId?: string,
  range: TimeRange = "all",
  filters: { model?: string; environment?: string } = {},
): Promise<TraceSummary | null> {
  const params = new URLSearchParams();
  if (projectId) params.set("project_id", projectId);
  const since = rangeSince(range);
  if (since) params.set("since", since);
  if (filters.model) params.set("model", filters.model);
  if (filters.environment) params.set("environment", filters.environment);
  try {
    const response = await fetch(`${API_BASE_URL}/v1/metrics/summary?${params}`, {
      cache: "no-store",
      headers: serverHeaders(),
    });
    if (!response.ok) return null;
    const data = (await response.json()) as {
      total: number;
      healthy: number;
      by_diagnosis: Record<string, number>;
      by_source: Record<string, number>;
      by_model?: Record<string, number>;
      by_environment?: Record<string, number>;
      latency_ms: TraceSummary["latencyMs"];
      cost_usd: TraceSummary["costUsd"];
    };
    return {
      total: data.total,
      healthy: data.healthy,
      byDiagnosis: data.by_diagnosis,
      bySource: data.by_source,
      byModel: data.by_model ?? {},
      byEnvironment: data.by_environment ?? {},
      latencyMs: data.latency_ms,
      costUsd: data.cost_usd,
    };
  } catch {
    return null;
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
  // True when the message is meant for the visitor as-is (rate limited, or the
  // playground is switched off); otherwise the UI shows a generic message.
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
  if (response.status === 404) {
    // Servers keep the playground off unless TRACEROAI_PLAYGROUND_ENABLED is set.
    throw new PlaygroundError("The live playground isn't enabled on this server.", true);
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
      headers: serverHeaders(),
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
      headers: serverHeaders(),
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
      headers: serverHeaders(),
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

export async function getTrace(traceId: string): Promise<Trace | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/v1/traces/${traceId}`, {
      cache: "no-store",
      headers: serverHeaders(),
    });

    if (!response.ok) {
      if (response.status !== 404) {
        console.error(`getTrace(${traceId}): the API answered ${response.status}`);
      }
      return null;
    }

    const trace = (await response.json()) as ApiTrace;
    return mapApiTraceToUiTrace(trace);
  } catch (error) {
    // The page shows "not found"; the server log says why.
    console.error(`getTrace(${traceId}) failed:`, error);
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
      headers: serverHeaders(),
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
      headers: serverHeaders(),
    });

    if (!response.ok) {
      return null;
    }

    return (await response.json()) as ApiEvalRun;
  } catch {
    return null;
  }
}


function mapApiTraceToUiTrace(trace: ApiTrace): Trace {
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
        // Leave unknowns empty rather than inventing labels or a 0 score.
        documentTitle: chunk.document_title || chunk.source || chunk.chunk_id,
        section: chunk.section || "",
        source: chunk.source || "",
        score: chunk.final_score ?? null,
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
            runId:
              typeof trace.metadata?.recovery_run_id === "string"
                ? trace.metadata.recovery_run_id
                : undefined,
            topK: typeof trace.metadata?.top_k === "number" ? trace.metadata.top_k : undefined,
          }
        : undefined,
    diagnosis: {
      label: normalizeDiagnosis(trace.diagnosis.label),
      reason: trace.diagnosis.reason || "No diagnosis available.",
      source: oneOf(trace.diagnosis.source, DIAGNOSIS_SOURCES),
    },
    deepStatus: oneOf(trace.evaluations.deep_status, DEEP_STATUSES),
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

  // What the experiment compared: the config keys whose values differ between
  // variants (bookkeeping keys aside).
  const configs = run.variants.map((v) => v.config ?? {});
  const compared = [...new Set(configs.flatMap((c) => Object.keys(c)))].filter(
    (key) => key !== "ungradeable_cases" && new Set(configs.map((c) => JSON.stringify(c[key]))).size > 1,
  );

  return {
    id: run.eval_run_id,
    type: "experiment",
    timestamp: run.timestamp,
    experimentName: run.dataset.name || run.pipeline.pipeline_version,
    comparedParameter: compared.join(", ") || "variant",
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
