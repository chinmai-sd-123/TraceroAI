# Media — screenshots & demo video

Drop the files below in this folder, then uncomment the image block near the top of
the root [`README.md`](../../README.md).

## Screenshots to capture (from the live app)

| File | What to capture | Notes |
|---|---|---|
| `dashboard.png` | The dashboard overview — trace list, the p95 latency card, the deep-eval queue panel | Use a real project with a spread of diagnoses. Width ~1600px. |
| `trace-detail.png` | A single trace detail page with the **diagnosis** visible — ideally a `retrieval_miss` or `unsupported_claim` so the "shows the cause" story lands | Show the retrieved chunks + per-stage breakdown. |
| `playground.png` | The `/docs` live playground after a query, showing the answer, the **`llm_judge`** badge, and the diagnosis | Capture the refund query showing `healthy_answer` via the LLM judge. |
| `demo.mp4` | 60–90s screen recording (see script below) | Export at 1080p; keep it under ~30 MB for GitHub. |

**Tips:** use the browser at a clean window size, dark theme (the app is dark by
default), and crop out the OS chrome. PNG for stills.

## Demo video script (~75 seconds)

1. **(0–10s) The hook.** Open the dashboard. Voiceover/caption: *"TraceroAI traces
   every RAG answer and tells you why a bad one was bad."*
2. **(10–30s) A failure.** Click into a trace diagnosed `retrieval_miss` (or
   `unsupported_claim`). Show the retrieved chunks and the diagnosis — *"the right
   document was never retrieved."*
3. **(30–50s) The quick→deep story.** Go to `/docs`, ask "How long does a refund
   take?". Show it answered correctly, with the **`llm_judge`** badge — *"the fast
   deterministic check is brittle on short queries; the LLM judge corrects it live."*
4. **(50–65s) The SDK.** Cut to the quickstart code on `/docs`. *"Add it to any RAG
   app in a few lines — `pip install traceroai`."*
5. **(65–75s) Close.** Back to the dashboard. *"Observability and evaluation for RAG,
   built like production infrastructure."* End on the live URL.

Keep it tight — no dead air, no loading screens (record after the Render cold start).
