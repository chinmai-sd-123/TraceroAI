# Field trial 1: LibreChat's rag_api

We pointed TraceroAI at a real RAG service it wasn't built around, used its diagnoses
to improve the answers, and checked the results by hand. It found one real fix in the
pipeline, and four places where TraceroAI itself needed work. Three are fixed; the
fourth is measured and scheduled.

## Setup

| | |
|---|---|
| Project | [LibreChat-AI/rag-api](https://github.com/LibreChat-AI/rag-api) (MIT) at `c4e5cbf`, the retrieval service behind LibreChat: FastAPI, LangChain, Postgres with pgvector |
| Documents | 12 pages of FastAPI's tutorial (MIT), fetched by `fetch_corpus.sh` |
| Questions | 32, drafted by `gpt-5.4-nano` from the pages. A pair was kept only if its supporting quote appears verbatim in the page; 16 of 48 drafts were dropped. 22 were used while making changes, 10 were held back to measure them |
| Answering | rag_api returns chunks; `trial.py` plays LibreChat's part and answers with `gpt-4o-mini` (temperature 0), using a prompt modelled on the one LibreChat wraps around rag_api's chunks |
| Judging | TraceroAI's LLM judge, `gpt-5.4-nano` |
| Cost | About 3 cents of generation, plus the judge's calls on the nano model |

rag_api's defaults were the baseline: 1,500-character chunks with 100 overlap, and the
top 4 chunks (LibreChat's default).

## What the diagnoses said

On the 22 tuning questions, TraceroAI's judge diagnosed each answer:

| Chunking | top-k | Prompt | Answered well | Other diagnoses |
|---|---|---|---|---|
| 1,500 / 100 | 4 | LibreChat-style | 15 | 5 unsupported claims, 2 retrieval misses |
| 1,500 / 100 | 4 | grounded | 19 | 2 correct refusals, 1 wrong answer |
| 1,500 / 100 | 6 | grounded | 18 | 2 correct refusals, 1 unsupported claim, 1 wrong answer |
| 800 / 150 | 6 | grounded | 20 | 1 correct refusal, 1 wrong answer |

Most failures were unsupported claims: the answer said more than the retrieved text.
The LibreChat-style prompt tells the model to use the context "as your learned
knowledge", which invites it to fill gaps from memory. One of those claims was wrong:
asked how middlewares are ordered, the answer said they run "from the innermost to the
outermost" on a request, and the FastAPI docs say the opposite. The judge's claim
check caught it and quoted the docs.

A prompt that keeps the answer to the context removed the unsupported claims (5 to 0).
Retrieving more chunks didn't help on its own. Smaller chunks changed the count by one
question, which is within noise at this size. The two "correct refusals" are questions
the documents do answer: retrieval missed the passage and the model declined instead
of guessing.

## What the held-back questions showed

`run_experiment` graded the 10 held-back questions for three setups. Then we read all
30 answers against the full question and expected answer.

| Setup | Experiment grader | By hand |
|---|---|---|
| Baseline | 7 / 10 | 9 / 10 |
| Grounded prompt | 8 / 10 | 10 / 10 |
| Grounded prompt, 800-character chunks | 9 / 10 | 9 / 10 |

The grader's 7 → 8 → 9 looks like a steady improvement. By hand there's no meaningful
difference: the grader failed answers that were right, mostly for leaving out a
secondary detail of the expected answer. Without checking the checker we would have
reported a gain that didn't happen.

The baseline was already correct because the documents are public: `gpt-4o-mini` knows
FastAPI, so its unsupported claims were usually true anyway. A grounded prompt still
matters, because it is what keeps answers honest on documents the model has never
seen. Showing a correctness gain needs a private corpus; that's a later trial.

## What it changed in TraceroAI

| Finding | Change |
|---|---|
| Experiments could only compare `top_k`; chunking and prompt settings in a variant never reached the pipeline | `retrieve` and `generate` can take a `variant` parameter (PR #62) |
| A judge-made diagnosis showed a fixed sentence written for the term-overlap estimate ("contains terms that are not supported") while the judge had named the wrong claim | The diagnosis uses the judge's reason and names the first unsupported claim |
| Issues grouped every failure by the top retrieved document, so five unsupported claims from one prompt became five issues | Grounding and answer failures are grouped by prompt version; on this data they become one issue |
| The experiment grader is noisy: the same grader on the same 30 answers agreed with the hand labels 24, 28 and 28 times in three runs | Two stricter prompts measured worse (26 and 25 of 30), so the prompt is unchanged. Grading each answer more than once and taking the majority is on the roadmap (multi-judge agreement) |

Grader measurements, from `grade_check.py` (two runs each, 30 answers, against the hand
labels):

| Grader | Agrees with hand labels | Same verdict in both runs |
|---|---|---|
| Current prompt | 28, 28 (24 in the experiment run) | 28 / 30 |
| Facts first | 26, 26 | 30 / 30 |
| Question-focused | 25, 25 | 28 / 30 |

## Run it again

1. Start TraceroAI with a provider key (see the main README) on port 8000.
2. Start pgvector and rag_api on port 8100, following rag_api's README, with
   `CHUNK_SIZE` and `CHUNK_OVERLAP` set for the setup you want.
3. `./fetch_corpus.sh`
4. From `services/api` in this repository:

```bash
python ../../field-trials/01-librechat-rag-api/trial.py ingest c1500
python ../../field-trials/01-librechat-rag-api/trial.py run c1500 4 librechat tune
python ../../field-trials/01-librechat-rag-api/trial.py experiment holdout \
  baseline:c1500:4:librechat grounded:c1500:4:grounded smaller:c800:6:grounded
```

The trial stops itself if its generation spend reaches 50 cents. Results land in the
`trial-rag-api` project in the dashboard. `results/holdout-graded.json` holds the 30
graded held-back answers this write-up is based on.
