import { mockTraces, type MockTrace, type TraceDiagnosis } from "./mock-traces";

type ApiTrace = {
  trace_id: string;
  timestamp: string;
  query: {
    original: string;
    rewritten?: string | null;
  };
  retrieval: {
    strategy: string;
    chunks: Array<{
      rank: number;
      chunk_id: string;
      document_title?: string | null;
      section?: string | null;
      source?: string | null;
      final_score?: number | null;
      text_preview?: string | null;
      text: string;
    }>;
  };
  generation: {
    model: string;
    answer: string;
  };
  latency: {
    total_ms?: number | null;
    retrieval_ms?: number | null;
    generation_ms?: number | null;
  };
  evaluations: {
    quick?: Array<{
      evaluator_name: string;
      label: string;
      score?: number | null;
      reason?: string | null;
    }>;
  };
  diagnosis: {
    label: TraceDiagnosis | string;
    reason?: string | null;
  };
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_TRACEROAI_API_URL || "http://127.0.0.1:8000";

export async function getTraces(): Promise<MockTrace[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/v1/traces`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return mockTraces;
    }

    const traces = (await response.json()) as ApiTrace[];
    return traces.map(mapApiTraceToUiTrace);
  } catch {
    return mockTraces;
  }
}

export async function getTrace(traceId: string): Promise<MockTrace | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/v1/traces/${traceId}`, {
      cache: "no-store",
    });

    if (response.status === 404) {
      return mockTraces.find((trace) => trace.traceId === traceId) || null;
    }

    if (!response.ok) {
      return mockTraces.find((trace) => trace.traceId === traceId) || null;
    }

    const trace = (await response.json()) as ApiTrace;
    return mapApiTraceToUiTrace(trace);
  } catch {
    return mockTraces.find((trace) => trace.traceId === traceId) || null;
  }
}

function mapApiTraceToUiTrace(trace: ApiTrace): MockTrace {
  const groundedness = findEval(trace, "groundedness");
  const contextRelevance = findEval(trace, "context_relevance");
  const answerRelevance = findEval(trace, "answer_relevance");

  return {
    traceId: trace.trace_id,
    timestamp: trace.timestamp,
    query: {
      original: trace.query.original,
      rewritten: trace.query.rewritten || undefined,
    },
    retrieval: {
      strategy: trace.retrieval.strategy,
      chunks: trace.retrieval.chunks.map((chunk) => ({
        rank: chunk.rank,
        chunkId: chunk.chunk_id,
        documentTitle: chunk.document_title || "Untitled document",
        section: chunk.section || "Unknown section",
        source: chunk.source || "unknown",
        relevance: "relevant",
        score: chunk.final_score ?? 0,
        textPreview: chunk.text_preview || chunk.text,
      })),
    },
    generation: {
      model: trace.generation.model,
      answer: trace.generation.answer,
    },
    latency: {
      totalMs: trace.latency.total_ms ?? 0,
      retrievalMs: trace.latency.retrieval_ms ?? 0,
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
    },
    diagnosis: {
      label: normalizeDiagnosis(trace.diagnosis.label),
      reason: trace.diagnosis.reason || "No diagnosis available.",
    },
  };
}

function findEval(trace: ApiTrace, evaluatorName: string) {
  return trace.evaluations.quick?.find(
    (item) => item.evaluator_name === evaluatorName,
  );
}

function normalizeDiagnosis(label: string): TraceDiagnosis {
  const knownLabels: TraceDiagnosis[] = [
    "healthy_answer",
    "retrieval_miss",
    "unsupported_claim",
    "low_context_relevance",
    "needs_review",
  ];

  if (knownLabels.includes(label as TraceDiagnosis)) {
    return label as TraceDiagnosis;
  }

  return "needs_review";
}
