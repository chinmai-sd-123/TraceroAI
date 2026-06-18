export type TraceDiagnosis =
  | "healthy_answer"
  | "correct_refusal"
  | "retrieval_miss"
  | "unsupported_claim"
  | "wrong_answer"
  | "low_context_relevance"
  | "needs_review";

export type MockTrace = {
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
      score: number;
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
  generation: {
    model: string;
    answer: string;
    costUsd?: number | null;
    totalTokens?: number | null;
  };
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
  recovery?: { attempt: number; action?: string };
  diagnosis: {
    label: TraceDiagnosis;
    reason: string;
  };
  feedback?: Array<{
    rating: string;
    comment?: string;
    createdAt?: string;
  }>;
};

export const mockTraces: MockTrace[] = [
  {
    traceId: "trace_healthy_region_change",
    timestamp: "2026-06-15T08:30:00Z",
    query: {
      original: "Can admins change the workspace region themselves?",
      rewritten: "Can admins change the workspace region themselves?",
    },
    retrieval: {
      strategy: "hybrid_rrf_rerank",
      chunks: [
        {
          rank: 1,
          chunkId: "product_faq_2",
          documentTitle: "Product FAQ",
          section: "Can I change my workspace region?",
          source: "product_faq.md",
          score: 1.08,
          textPreview:
            "Customers cannot directly change a workspace region after the workspace is created. To request a region change, customers must contact support.",
        },
        {
          rank: 2,
          chunkId: "onboarding_guide_1",
          documentTitle: "Customer Onboarding Guide",
          section: "Workspace Setup",
          source: "onboarding_guide.md",
          score: 0.38,
          textPreview:
            "Admins can configure workspace region during setup. Once a workspace is created, the customer cannot change the region without contacting support.",
        },
      ],
    },
    generation: {
      model: "gpt-4o-mini",
      answer:
        "No, admins cannot change the workspace region themselves. They must contact support to request a region change after the workspace is created [1], [2].",
    },
    latency: {
      totalMs: 1171,
      retrievalMs: 17,
      generationMs: 1154,
    },
    evaluations: {
      groundedness: {
        label: "grounded",
        score: 1,
        reason: "All answer claims are supported by retrieved evidence.",
      },
      contextRelevance: {
        label: "good_context",
        score: 0.9,
        reason: "The top retrieved chunks directly answer the query.",
      },
      answerRelevance: {
        label: "relevant",
        score: 1,
        reason: "The answer directly addresses workspace region changes.",
      },
    },
    diagnosis: {
      label: "healthy_answer",
      reason: "The retriever found useful context and the model answered the question.",
    },
  },
  {
    traceId: "trace_retrieval_miss_refund",
    timestamp: "2026-06-15T08:35:00Z",
    query: {
      original: "Can I get money back within 23 days?",
      rewritten: "Can I get a refund within 23 days?",
    },
    retrieval: {
      strategy: "vector",
      chunks: [
        {
          rank: 1,
          chunkId: "billing_processing_1",
          documentTitle: "Billing Processing",
          section: "Processing Times",
          source: "billing_processing.md",
          score: 0.47,
          textPreview:
            "Approved refunds are reviewed within 5 business days and may take 5 to 10 additional business days to appear.",
        },
        {
          rank: 2,
          chunkId: "account_cancellation_2",
          documentTitle: "Account Cancellation",
          section: "Cancellation Flow",
          source: "account_cancellation.md",
          score: 0.41,
          textPreview:
            "Customers can cancel subscriptions from account settings. Cancellation does not automatically delete workspace data.",
        },
      ],
    },
    generation: {
      model: "gpt-4o-mini",
      answer:
        "No, refunds may take up to 15 business days to process after review.",
    },
    latency: {
      totalMs: 3684,
      retrievalMs: 1390,
      generationMs: 2294,
    },
    evaluations: {
      groundedness: {
        label: "partially_grounded",
        score: 0.5,
        reason: "The answer uses retrieved processing-time context but misses the refund eligibility window.",
      },
      contextRelevance: {
        label: "weak_context",
        score: 0.45,
        reason: "The expected refund policy chunk was not retrieved.",
      },
      answerRelevance: {
        label: "partially_relevant",
        score: 0.6,
        reason: "The answer discusses refunds but answers processing time, not eligibility.",
      },
    },
    diagnosis: {
      label: "retrieval_miss",
      reason: "The expected refund policy document was not retrieved, so the model answered from incomplete evidence.",
    },
  },
  {
    traceId: "trace_unsupported_phone_support",
    timestamp: "2026-06-15T08:42:00Z",
    query: {
      original: "Does Acme Cloud offer phone support?",
      rewritten: "Does Acme Cloud offer phone support?",
    },
    retrieval: {
      strategy: "hybrid_rrf_rerank",
      chunks: [
        {
          rank: 1,
          chunkId: "support_policy_1",
          documentTitle: "Support Policy",
          section: "Support Channels",
          source: "support_policy.md",
          score: 0.64,
          textPreview:
            "Acme Cloud offers email support for all customers. Acme Cloud does not offer phone support for self-serve monthly or annual plans.",
        },
      ],
    },
    generation: {
      model: "gpt-4o-mini",
      answer:
        "Yes, Acme Cloud offers phone support for enterprise and self-serve customers.",
    },
    latency: {
      totalMs: 2108,
      retrievalMs: 320,
      generationMs: 1788,
    },
    evaluations: {
      groundedness: {
        label: "unsupported",
        score: 0.1,
        reason: "The answer contradicts the retrieved support policy.",
      },
      contextRelevance: {
        label: "good_context",
        score: 1,
        reason: "The retrieved chunk directly addresses phone support.",
      },
      answerRelevance: {
        label: "relevant",
        score: 1,
        reason: "The answer is on-topic but factually unsupported.",
      },
    },
    diagnosis: {
      label: "unsupported_claim",
      reason: "The correct evidence was retrieved, but the model generated a claim contradicted by the context.",
    },
  },
];