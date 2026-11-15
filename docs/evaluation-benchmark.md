# Diagnosis accuracy

How often each evaluation tier assigns the right diagnosis, measured on a labelled set
of 117 traces. Run on 2026-11-13; the full report, with every verdict, is in
[`benchmarks/2026-11-13-diagnosis.json`](benchmarks/2026-11-13-diagnosis.json).

| Tier | When it runs | Accuracy |
|---|---|---|
| Lexical (term overlap) | at ingest, no network | 58.1% (68/117) |
| Embedding (`text-embedding-3-small`) | background, when a provider key is set | 76.1% (89/117) |
| LLM judge (`gpt-5.4-nano-2026-03-17`) | background, when a provider key is set | 94.0%–95.7% over 3 runs |

The judge gave the same label in all three runs for 96.6% of cases.

## Per label

Precision is how often a label is right when it's given; recall is how many of the cases
with that label it finds.

| Label | Cases | Lexical P / R | Embedding P / R | Judge P / R |
|---|---|---|---|---|
| `healthy_answer` | 22 | 1.00 / 0.14 | 0.93 / 0.64 | 0.95 / 0.95 |
| `correct_refusal` | 18 | 0.56 / 1.00 | 0.94 / 0.94 | 1.00 / 0.94 |
| `retrieval_miss` | 20 | 0.53 / 1.00 | 1.00 / 0.85 | 1.00 / 0.95 |
| `unsupported_claim` | 21 | 0.92 / 0.52 | 0.77 / 0.62 | 0.81 / 1.00 |
| `wrong_answer` | 36 | 0.73 / 0.44 | 0.97 / 0.78 | 0.97 / 0.89 |

Judge figures are from the first of the three runs.

## What the numbers say

- **Lexical diagnoses aren't usable on their own.** Term overlap almost never recognises a
  correct answer that's worded differently from the source (3 of 22 healthy answers), and
  it labels most refusals as correct even when the context held the answer. The dashboard
  marks these diagnoses as estimates, and the recovery agent doesn't retry on them by
  default.
- **The embedding tier is mostly undecided rather than wrong.** 21 of its 28 misses are
  `needs_review`, where the similarity falls between the pass and fail thresholds.
- **The judge's misses share one pattern.** An answer drawn from the context but reworded
  ("outside auditors" for "third-party auditors") is sometimes judged unsupported. It also
  treated refund text as relevant to a question about failed payments, which turned one
  miss into two.

## The test set

- **9 hand-labelled traces** in `services/api/app/eval/golden_traces.json`.
- **108 constructed traces** from `services/api/app/eval/constructed_cases.py`: 18 facts
  from the demo knowledge base, each turned into six traces whose correct diagnosis
  follows from how they're built (a correct paraphrase, the same plus an invented claim,
  the right answer over unrelated context, a refusal over unrelated context, a refusal
  over the right context, and an answer about a neighbouring fact).

The constructed labels are definitional, not observed: they follow the diagnosis
definitions rather than human judgement of real traffic. All cases come from one small
support-style knowledge base with short answers. Treat the figures as a comparison
between tiers and a regression baseline, not as accuracy on production data.

## Reproducing

From `services/api`, with `TRACEROAI_OPENAI_API_KEY` set (about 1,200 provider calls):

```bash
python -m app.eval.benchmark --repeat 3 --report results.json
python -m app.eval.benchmark --no-provider     # lexical tier only, offline
```

CI runs the lexical tier on every change (`tests/test_regression_gate.py`) and fails if
it drops below 58% on the full set or 75% on the hand-labelled cases.
