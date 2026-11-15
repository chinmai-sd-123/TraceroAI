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
