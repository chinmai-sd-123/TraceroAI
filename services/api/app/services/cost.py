"""Server-side cost computation for traces.

The SDK sends token counts (it has them from the LLM response); the server is the
source of truth for *pricing*, so cost is computed here from a small price table.
Prices are USD per 1,000 tokens (input, output). Unknown models cost 0 (we don't
guess), so a missing model never inflates the bill.
"""

from __future__ import annotations

from app.schemas.traces import UsageTrace

# USD per 1K tokens: (input, output). Extend as you add models.
_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.0025, 0.01),
    "gpt-4.1-mini": (0.0004, 0.0016),
    "text-embedding-3-small": (0.00002, 0.0),
    "gemini-2.5-flash": (0.0003, 0.0025),
    "gemini-2.5-flash-lite": (0.0001, 0.0004),
}


def price_for(model: str | None) -> tuple[float, float] | None:
    if not model:
        return None
    # Exact match, else a prefix match (e.g. dated model ids like gpt-4o-mini-2024-..).
    if model in _PRICES:
        return _PRICES[model]
    for known, price in _PRICES.items():
        if model.startswith(known):
            return price
    return None


def compute_cost_usd(model: str | None, usage: UsageTrace) -> float | None:
    """Cost in USD from token counts + the model's price. Returns None if we can't
    price it (unknown model or no token counts) — never a fabricated number."""
    price = price_for(model)
    if price is None:
        return None
    if usage.prompt_tokens is None and usage.completion_tokens is None:
        return None
    in_price, out_price = price
    prompt = usage.prompt_tokens or 0
    completion = usage.completion_tokens or 0
    cost = (prompt / 1000) * in_price + (completion / 1000) * out_price
    return round(cost, 6)
