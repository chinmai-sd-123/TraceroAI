export type RegressionEvalRun = {
  id: string;
  type: "regression";
  timestamp: string;
  pipelineVersion: string;
  datasetName: string;
  summary: {
    totalCases: number;
    passedCases: number;
    failedCases: number;
    overallAccuracy: number;
    statusAccuracy: number;
    retrievalAccuracy: number;
    failureLabelAccuracy: number;
    avgLatencyMs: number;
  };
};

export type ExperimentEvalRun = {
  id: string;
  type: "experiment";
  timestamp: string;
  experimentName: string;
  comparedParameter: string;
  values: Array<{
    value: string;
    healthyRate: number;
    sourceRecallRate: number;
    contextPrecision: number;
    avgLatencyMs: number;
  }>;
  recommendation: {
    value: string;
    reason: string;
  };
};

export const regressionRuns: RegressionEvalRun[] = [
  {
    id: "eval_regression_hybrid_rrf_v1",
    type: "regression",
    timestamp: "2026-06-15T09:10:00Z",
    pipelineVersion: "hybrid_rrf_rerank_v1",
    datasetName: "acme_policy_eval",
    summary: {
      totalCases: 7,
      passedCases: 7,
      failedCases: 0,
      overallAccuracy: 100,
      statusAccuracy: 100,
      retrievalAccuracy: 100,
      failureLabelAccuracy: 100,
      avgLatencyMs: 1101,
    },
  },
];

export const experimentRuns: ExperimentEvalRun[] = [
  {
    id: "eval_top_k_comparison_v1",
    type: "experiment",
    timestamp: "2026-06-15T09:20:00Z",
    experimentName: "Top-K Retrieval Comparison",
    comparedParameter: "top_k",
    values: [
      {
        value: "1",
        healthyRate: 80,
        sourceRecallRate: 100,
        contextPrecision: 100,
        avgLatencyMs: 2631,
      },
      {
        value: "2",
        healthyRate: 100,
        sourceRecallRate: 100,
        contextPrecision: 100,
        avgLatencyMs: 2152,
      },
      {
        value: "3",
        healthyRate: 100,
        sourceRecallRate: 100,
        contextPrecision: 100,
        avgLatencyMs: 1942,
      },
      {
        value: "5",
        healthyRate: 100,
        sourceRecallRate: 100,
        contextPrecision: 100,
        avgLatencyMs: 2731,
      },
    ],
    recommendation: {
      value: "3",
      reason:
        "Selected the smallest top_k with perfect healthy rate and the lowest average latency among passing configs.",
    },
  },
];