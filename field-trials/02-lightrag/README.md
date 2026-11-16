# Field trial 2: LightRAG

LightRAG answers from a knowledge graph it builds out of your documents. We gave it
documentation the answering model can't have seen, traced every answer with
TraceroAI, and compared its default settings with smaller ones. The defaults sent
three times the context for no measured gain in quality. The trial also showed that
TraceroAI's experiments didn't record cost; they do now.

## Setup

| | |
|---|---|
| Project | [HKUDS/LightRAG](https://github.com/HKUDS/LightRAG) (MIT) at `9234426`, version 1.5.8, with the official OpenAI setup (`gpt_4o_mini_complete`, `openai_embed`) |
| Documents | Six pages of LightRAG's own documentation (about 85,000 characters), fetched by `fetch_corpus.sh`. They were written in 2025–2026, after `gpt-4o-mini`'s training data, so the model can't answer from memory |
| Questions | 30, drafted by `gpt-5.4-nano` and kept only if their supporting quote appears verbatim in the page (12 of 42 drafts were dropped). 20 were used while making changes, 10 were held back |
| Tracing | `aquery_llm` returns the chunks LightRAG used and its answer; both go into the trace |
| Judging | TraceroAI's LLM judge, `gpt-5.4-nano` |
| Cost | 29 cents in all: 3.6 for building the graph, the rest for answering. Judge calls on the nano model come on top |

## What TraceroAI showed

On the 20 tuning questions, with each answer's diagnosis, prompt size and cost from
its trace:

| Query mode | top_k / chunk_top_k | Healthy (of 20) | Median prompt tokens | Cost per healthy answer | Median latency |
|---|---|---|---|---|---|
| `mix` (default) | 40 / 20 (defaults) | 16 | 29,883 | 0.58¢ | 11.1 s |
| `mix` | 20 / 8 | 17 | 14,241 | 0.27¢ | 7.0 s |
| `naive` (vector only) | 8 chunks | 17, and 1 wrong answer | 9,518 | 0.19¢ | 6.0 s |

The failures were unsupported claims: small overreaches, such as saying LightRAG
"automatically adopts" a cache directory where the docs say it does so only if the
directory exists. The diagnosis now quotes each claim (a fix from trial 1), and all
four baseline claims formed one issue, "prompt lightrag-mix", instead of four.

The bigger finding is cost. LightRAG's defaults fill the context up to its 30,000-token
budget for questions a few paragraphs answer. Smaller settings were at least as good
and a third to a half of the cost, and 37–46% faster.

## Held-back questions

The experiment graded the 10 held-back questions; then we read all 30 answers against
the full question and expected answer.

| Setup | Experiment grader | By hand |
|---|---|---|
| `mix`, defaults | 8 / 10 | 8 / 10 |
| `mix`, 20 / 8 | 7 / 10 | 8 / 10 |
| `naive`, 8 chunks | 8 / 10 | 10 / 10 |

With 10 questions, the honest reading is "no worse", not "better". The grader disagreed
with the hand labels on 5 of 30 answers, the same rate as trial 1. Four were false
failures: three correct, thorough answers to the MinerU question that included extra
correct steps from the docs, and one answer that stated the key facts. One was a false
pass: an answer that said a chunk's `tokens` field is a list of integers, where the docs
say it's an int.

## What it changed in TraceroAI

| Finding | Change |
|---|---|
| Experiments recorded accuracy and latency per variant, not tokens or cost, though cost was the difference that mattered | `generate` can return `(answer, usage)`; each variant reports its token totals, the server prices them, and the experiment page shows tokens per answer and cost per correct answer |
| The experiment grader again disagreed with hand labels on 5 of 30, mostly by failing long, correct answers | Confirms trial 1. Majority grading (multi-judge agreement) moves up the roadmap |

Fixes from trial 1 held up on new data: diagnoses named the unsupported claim, and one
prompt-level cause appeared as one issue.

## Run it again

1. Start TraceroAI with a provider key on port 8000.
2. `pip install lightrag-hku==1.5.8` (or LightRAG at `9234426`) in its own virtualenv,
   and set `OPENAI_API_KEY`.
3. `./fetch_corpus.sh`
4. With that virtualenv:

```bash
python trial.py index
python trial.py run mix 40 20 tune
python trial.py run naive 20 8 tune
python trial.py experiment holdout default:mix:40:20 smaller:mix:20:8 naive:naive:20:8
```

The trial stops itself at 50 cents of model spend. LightRAG caches answers, so a repeat
query reports no tokens; build a fresh index (`results/index`) for full cost numbers.
`results/holdout-graded.json` holds the 30 graded held-back answers this write-up is
based on.
