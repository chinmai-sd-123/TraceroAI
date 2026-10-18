import httpx
import pytest

from app.schemas.traces import UsageTrace
from app.services import cost


def _no_network(*args, **kwargs):
    raise AssertionError("pricing must not fetch on the request path")


def test_pricing_never_fetches_and_uses_builtin_table_until_loaded(monkeypatch) -> None:
    monkeypatch.setattr(cost, "_litellm_cache", {})
    monkeypatch.setattr(httpx, "get", _no_network)

    usage = UsageTrace(prompt_tokens=1000, completion_tokens=1000)
    # gpt-4o-mini from the built-in table: 0.00015 + 0.0006 per 1k tokens.
    assert cost.compute_cost_usd("gpt-4o-mini", usage) == pytest.approx(0.00075)
    assert cost.compute_cost_usd("some-unknown-model", usage) is None


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_refresh_loads_prices_and_they_take_precedence(monkeypatch) -> None:
    monkeypatch.setattr(cost, "_litellm_cache", {})
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *a, **k: _FakeResponse(
            {
                "gpt-4o-mini": {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
                "sample_spec": "not a model entry",
            }
        ),
    )

    assert cost.refresh_litellm_prices() is True
    assert cost.price_for("gpt-4o-mini") == pytest.approx((0.001, 0.002))


def test_failed_refresh_keeps_previous_prices(monkeypatch) -> None:
    monkeypatch.setattr(cost, "_litellm_cache", {"gpt-4o-mini": (0.5, 0.5)})

    def _boom(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "get", _boom)

    assert cost.refresh_litellm_prices() is False
    assert cost.price_for("gpt-4o-mini") == (0.5, 0.5)
