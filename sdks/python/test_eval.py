"""Tests for the client-usable eval harness (traceroai.eval).

Run from sdks/python:  python -m pytest test_eval.py
No live API/LLM — httpx.post is monkeypatched so the harness orchestration is
tested deterministically (the server grades in production).
"""

import traceroai.eval as E
from traceroai import TraceroClient
from traceroai.eval import Case, Variant, run_experiment


class _FakeResp:
    def __init__(self, status: int, payload: dict) -> None:
        self.status_code = status
        self._payload = payload

    @property
    def text(self) -> str:
        return str(self._payload)

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _patch_server(monkeypatch, *, correct_if, grade_status: int = 200) -> dict:
    """Patch httpx.post: /grade returns correct=correct_if(answer); /eval-runs 201."""
    calls = {"grade": 0, "post_run": 0}

    def fake_post(url, json=None, headers=None, timeout=None):
        if url.endswith("/v1/eval/grade"):
            calls["grade"] += 1
            if grade_status != 200:
                return _FakeResp(grade_status, {})
            return _FakeResp(200, {"correct": correct_if(json["actual"]), "reason": "stub"})
        if url.endswith("/v1/eval-runs"):
            calls["post_run"] += 1
            return _FakeResp(201, {"eval_run_id": "run-abc"})
        raise AssertionError(f"unexpected POST {url}")

    monkeypatch.setattr(E.httpx, "post", fake_post)
    return calls


def _retrieve(query, top_k):
    return [{"text": f"ctx for {query} (k={top_k})"}]


def _client():
    return TraceroClient(base_url="http://test", api_key="demo_key")


def test_run_experiment_grades_and_posts(monkeypatch):
    calls = _patch_server(monkeypatch, correct_if=lambda a: "refund" in a.lower())

    def generate(query, ctx):
        return "Refunds take 5-7 business days." if "refund" in query.lower() else "other"

    dataset = [
        Case("c1", "How long does a refund take?", "5-7 business days"),
        Case("c2", "Where is my refund sent?", "original payment method"),
    ]
    result = run_experiment(
        client=_client(), dataset=dataset, retrieve=_retrieve, generate=generate,
        variants=[Variant("k3", "top_k=3", top_k=3), Variant("k5", "top_k=5", top_k=5)],
        project_id="t",
    )

    assert result.eval_run_id == "run-abc"
    assert calls["grade"] == 4  # 2 cases x 2 variants
    assert calls["post_run"] == 1
    for v in result.variants:
        assert any(m["metric_name"] == "accuracy" for m in v["metrics"])


def test_ungradeable_not_counted_as_failed(monkeypatch):
    # Grading unavailable (503) -> cases are ungradeable, not failures.
    _patch_server(monkeypatch, correct_if=lambda a: True, grade_status=503)

    result = run_experiment(
        client=_client(), dataset=[Case("c1", "q", "e")],
        retrieve=_retrieve, generate=lambda q, c: "ans",
        variants=[Variant("a", "A"), Variant("b", "B")], project_id="t",
    )
    for v in result.variants:
        assert v["passed_cases"] == 0
        assert v["failed_cases"] == 0  # not counted wrong
        assert v["config"]["ungradeable_cases"] == 1


def test_winner_is_highest_accuracy(monkeypatch):
    # Only the k5 variant's answers are graded correct -> k5 should win.
    def fake_post(url, json=None, headers=None, timeout=None):
        if url.endswith("/v1/eval/grade"):
            return _FakeResp(200, {"correct": "k=5" in json["actual"], "reason": "x"})
        return _FakeResp(201, {"eval_run_id": "r"})

    monkeypatch.setattr(E.httpx, "post", fake_post)

    def generate(query, ctx):
        return f"answer ({ctx.split('(')[-1]}"  # embeds 'k=N)' from the context

    result = run_experiment(
        client=_client(), dataset=[Case("c1", "q", "e")],
        retrieve=_retrieve, generate=generate,
        variants=[Variant("k3", "top_k=3", top_k=3), Variant("k5", "top_k=5", top_k=5)],
        project_id="t",
    )
    assert "k5" in result.recommendation


def test_requires_two_variants(monkeypatch):
    _patch_server(monkeypatch, correct_if=lambda a: True)
    import pytest

    with pytest.raises(ValueError):
        run_experiment(
            client=_client(), dataset=[Case("c1", "q", "e")],
            retrieve=_retrieve, generate=lambda q, c: "a",
            variants=[Variant("a", "A")], project_id="t",
        )


def test_a_failed_upload_keeps_the_results(monkeypatch) -> None:
    def fake_post(url, json=None, headers=None, timeout=None):
        if url.endswith("/v1/eval/grade"):
            return _FakeResp(200, {"correct": True, "reason": "stub"})
        raise E.httpx.ConnectError("API unreachable")

    monkeypatch.setattr(E.httpx, "post", fake_post)
    result = run_experiment(
        client=TraceroClient(base_url="http://x", flush_on_exit_seconds=0),
        dataset=[Case("c1", "q", "a")],
        retrieve=lambda q, k: [{"text": "ctx"}],
        generate=lambda q, c: "a",
        variants=[Variant("v1", "one", top_k=1), Variant("v2", "two", top_k=2)],
    )

    assert result.eval_run_id is None
    assert len(result.variants) == 2  # the paid-for results are still here
    assert any("posting the eval run failed" in e for e in result.errors)


def test_ungradeable_cases_say_why(monkeypatch) -> None:
    _patch_server(monkeypatch, correct_if=lambda a: True, grade_status=503)
    result = run_experiment(
        client=TraceroClient(base_url="http://x", flush_on_exit_seconds=0),
        dataset=[Case("c1", "q", "a")],
        retrieve=lambda q, k: [],
        generate=lambda q, c: "a",
        variants=[Variant("v1", "one"), Variant("v2", "two")],
        post=False,
    )
    assert result.errors and "HTTP 503" in result.errors[0]


def test_experiment_sends_each_graded_question_per_variant(monkeypatch):
    sent: dict = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        if url.endswith("/v1/eval/grade"):
            # c2 can't be graded for the first variant.
            if "where" in json["question"].lower() and "k=3" in json["actual"]:
                return _FakeResp(503, {})
            return _FakeResp(200, {"correct": "refund" in json["actual"].lower()})
        sent.update(json)
        return _FakeResp(201, {"eval_run_id": "run-abc"})

    monkeypatch.setattr(E.httpx, "post", fake_post)
    dataset = [Case("c1", "How long does a refund take?", "5-7 days"), Case("c2", "Where is it sent?", "card")]
    result = run_experiment(
        client=_client(), dataset=dataset, retrieve=_retrieve,
        generate=lambda q, ctx: f"refund answer {ctx}" if "refund" in q.lower() else f"other {ctx}",
        variants=[Variant("k3", "top_k=3", top_k=3), Variant("k5", "top_k=5", top_k=5)],
    )

    assert [(c["variant_id"], c["case_id"], c["passed"]) for c in sent["cases"]] == [
        ("k3", "c1", True), ("k5", "c1", True), ("k5", "c2", False),
    ]  # the ungradeable case isn't sent
    assert len(result.cases) == 4  # but the caller sees every case
    assert next(c for c in result.cases if c["variant_id"] == "k3" and c["case_id"] == "c2")["passed"] is None


def test_an_older_server_still_gets_the_totals(monkeypatch):
    posts: list[dict] = []

    def fake_post(url, json=None, headers=None, timeout=None):
        if url.endswith("/v1/eval/grade"):
            return _FakeResp(200, {"correct": True})
        posts.append(json)
        # Older servers reject experiment cases.
        return _FakeResp(422, {}) if json["cases"] else _FakeResp(201, {"eval_run_id": "run-old"})

    monkeypatch.setattr(E.httpx, "post", fake_post)
    result = run_experiment(
        client=_client(), dataset=[Case("c1", "q", "a")], retrieve=_retrieve, generate=lambda q, c: "a",
        variants=[Variant("k3", "a", top_k=3), Variant("k5", "b", top_k=5)],
    )

    assert result.eval_run_id == "run-old"
    assert [len(p["cases"]) for p in posts] == [2, 0]
    assert any("per-question" in e for e in result.errors)


def test_variant_settings_reach_retrieve_and_generate(monkeypatch):
    # Comparing chunking or prompts, not just top_k: functions that declare a
    # `variant` parameter get the variant being run.
    _patch_server(monkeypatch, correct_if=lambda a: a.startswith("strict"))
    seen = []

    def retrieve(query, top_k, variant):
        seen.append(("retrieve", variant.variant_id, variant.extra["chunking"]))
        return [{"text": "ctx"}]

    def generate(query, ctx, variant):
        seen.append(("generate", variant.variant_id, variant.extra["prompt"]))
        return f"{variant.extra['prompt']} answer"

    result = run_experiment(
        client=_client(),
        dataset=[Case("c1", "q", "a")],
        retrieve=retrieve,
        generate=generate,
        variants=[
            Variant("base", "default prompt", extra={"prompt": "plain", "chunking": "1500/100"}),
            Variant("strict", "strict prompt", extra={"prompt": "strict", "chunking": "800/200"}),
        ],
        post=False,
    )

    assert seen == [
        ("retrieve", "base", "1500/100"),
        ("generate", "base", "plain"),
        ("retrieve", "strict", "800/200"),
        ("generate", "strict", "strict"),
    ]
    by_id = {v["variant_id"]: v for v in result.variants}
    assert by_id["strict"]["passed_cases"] == 1 and by_id["base"]["passed_cases"] == 0


def test_two_argument_functions_still_work(monkeypatch):
    _patch_server(monkeypatch, correct_if=lambda a: True)
    result = run_experiment(
        client=_client(),
        dataset=[Case("c1", "q", "a")],
        retrieve=_retrieve,
        generate=lambda query, ctx: "answer",
        variants=[Variant("k3", "k3", top_k=3), Variant("k5", "k5", top_k=5)],
        post=False,
    )
    assert all(v["passed_cases"] == 1 for v in result.variants)
