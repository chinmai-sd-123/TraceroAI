// The hero's backdrop: the stored record of a real trace (5f7bf901 from the
// example app), set faintly in monospace like a printout under the report.
// The spotlight layer repeats it in navy so the cursor can read it.

const RECORD = `{
  "trace_id": "5f7bf901-ba0b-431d-a5e4-2bf8c8f57869",
  "project": { "project_id": "recovery-agent", "environment": "dev" },
  "query": { "original": "is money within 10 days refunded?" },
  "retrieval": {
    "strategy": "vector",
    "config": { "final_top_k": 3 },
    "chunks": [
      { "rank": 1, "document_title": "refund-policy",
        "text": "Refunds are processed within 5 to 7 business days after the request is approved. The approval review itself typically completes within 1 business day of submission." },
      { "rank": 2, "document_title": "refund-policy",
        "text": "Refunds are always issued to the original payment method used for the purchase." },
      { "rank": 3, "document_title": "refund-policy",
        "text": "Subscriptions can be refunded within 14 days of renewal." }
    ]
  },
  "generation": {
    "model": "gpt-4o-mini",
    "answer": "Yes, money is typically refunded within 10 days, as refunds are processed within 5 to 7 business days after approval.",
    "usage": { "total_tokens": 410 }
  },
  "latency": { "retrieval_ms": 223, "generation_ms": 1451, "total_ms": 1680 },
  "evaluations": {
    "quick": [
      { "name": "context_relevance", "label": "pass" },
      { "name": "groundedness", "label": "needs_review" },
      { "name": "answer_relevance", "label": "pass" }
    ],
    "deep": [
      { "name": "deep_context_relevance", "label": "relevant" },
      { "name": "claim_groundedness", "label": "not_grounded",
        "reason": "1 of 4 claims are not supported by the context.",
        "claims": [
          { "claim": "Money is typically refunded within 10 days.", "supported": false },
          { "claim": "Refunds are processed within 5 to 7 business days after the request is approved.", "supported": true },
          { "claim": "Approval review typically completes within 1 business day of submission.", "supported": true },
          { "claim": "Most customers receive their full refund within a week and a half at most.", "supported": true }
        ] },
      { "name": "deep_answer_relevance", "label": "relevant" }
    ]
  },
  "diagnosis": { "label": "unsupported_claim", "source": "judge" },
  "metadata": { "agent": "recovery", "attempt": 2, "recovery_action": "tighten_generation" }
}`;

export function TraceRecord({ className = "" }: { className?: string }) {
  return (
    <div aria-hidden="true" className={`trace-record pointer-events-none absolute inset-0 overflow-hidden select-none ${className}`}>
      <div className="trace-record-cols">
        {[0, 1, 2].map((col) => (
          <pre key={col} className="trace-record-text">
            {RECORD}
          </pre>
        ))}
      </div>
    </div>
  );
}
