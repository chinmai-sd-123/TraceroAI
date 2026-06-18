# RAG experiment evaluation (via the TraceroAI SDK)

A/B-test your RAG pipeline configs against a labeled dataset and see the result on
the dashboard — using `traceroai.eval`. This example is a **client** of TraceroAI:
it brings its own pipeline + dataset; the platform only grades and stores.

```python
from traceroai import TraceroClient
from traceroai.eval import run_experiment, Case, Variant

run_experiment(
    client=TraceroClient(base_url=..., api_key=...),
    dataset=[Case("c1", "How long does a refund take?", "5-7 business days.")],
    retrieve=my_retrieve,   # (query, top_k) -> list[chunk dict]
    generate=my_generate,   # (query, context) -> answer str
    variants=[Variant("k3", "top_k=3", top_k=3), Variant("k5", "top_k=5", top_k=5)],
    project_id="my-app",
)
```

Each case is run through every variant, graded against its expected answer by
TraceroAI's **server-side LLM judge** (single source of truth — same judge as the
dashboard), and the highest-accuracy variant is recommended. The run is posted to
your project's dashboard under **Eval Runs**.

## Run

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
export TRACEROAI_API_URL=https://traceroai.onrender.com
export TRACEROAI_API_KEY=your_project_key
python app.py
```

`dataset.py` holds the labeled cases; `app.py` wires a small LangChain retriever +
`ChatOpenAI` generator. Swap in your own pipeline and dataset to evaluate your app.
