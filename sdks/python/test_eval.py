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
