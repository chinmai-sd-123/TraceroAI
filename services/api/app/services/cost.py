"""Server-side cost computation for traces.

The SDK sends token counts (from the LLM response); the server owns *pricing* and
computes cost here. Prices come from two sources, in order:
  1. the live, community-maintained LiteLLM pricing map (fetched once + cached) —
     covers ~thousands of models and stays current as providers change prices, and
  2. a small built-in table (below) as a fail-open fallback if the map is
     unreachable.
A client may also send an exact `cost_usd` on the trace's usage, which takes
precedence over both (see the ingest route). Unknown models return None — we never
guess, so a missing price can't inflate cost.

Model ids are matched exact-first, then by longest prefix (so dated ids like
"gpt-4o-mini-2024-07-18" resolve to "gpt-4o-mini", and "gpt-4o-mini" wins over
"gpt-4o"). Prices are stored as USD per 1,000 tokens (input, output).
"""

from __future__ import annotations

import threading

import httpx

from app.schemas.traces import UsageTrace

# LiteLLM publishes a community-maintained pricing map as plain JSON (no need for
# the heavy litellm library). We fetch it once, cache it, and use it as the primary
# price source; the small hardcoded table below is the fail-open fallback.
_LITELLM_PRICES_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
    "model_prices_and_context_window.json"
)
_litellm_cache: dict[str, tuple[float, float]] | None = None
_litellm_lock = threading.Lock()


def _load_litellm_prices() -> dict[str, tuple[float, float]]:
    """Fetch + cache the LiteLLM pricing map as {model: (input_per_1k, output_per_1k)}.

    Cached for the process lifetime. On any failure returns {} so callers fall back
    to the built-in table — pricing is best-effort, never a hard dependency.
    """
    global _litellm_cache
    if _litellm_cache is not None:
        return _litellm_cache
    with _litellm_lock:
        if _litellm_cache is not None:
            return _litellm_cache
        prices: dict[str, tuple[float, float]] = {}
        try:
            resp = httpx.get(_LITELLM_PRICES_URL, timeout=5.0)
            resp.raise_for_status()
            for model, info in resp.json().items():
                if not isinstance(info, dict):
                    continue
                # LiteLLM prices are USD per *token*; convert to per-1k.
                inp = info.get("input_cost_per_token")
                out = info.get("output_cost_per_token")
                if inp is None and out is None:
                    continue
                prices[model] = ((inp or 0.0) * 1000, (out or 0.0) * 1000)
        except Exception:
            prices = {}
        _litellm_cache = prices
        return _litellm_cache

# USD per 1K tokens: (input_price, output_price).
_PRICES: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.0025, 0.01),
    "gpt-4.1-mini": (0.0004, 0.0016),
    "gpt-4.1-nano": (0.0001, 0.0004),
    "gpt-4.1": (0.002, 0.008),
    "o4-mini": (0.0011, 0.0044),
    "o3-mini": (0.0011, 0.0044),
    # OpenAI embeddings (no output tokens)
    "text-embedding-3-small": (0.00002, 0.0),
    "text-embedding-3-large": (0.00013, 0.0),
    # Google Gemini
    "gemini-2.5-flash": (0.0003, 0.0025),
    "gemini-2.5-flash-lite": (0.0001, 0.0004),
    "gemini-2.5-pro": (0.00125, 0.01),
    "gemini-embedding-001": (0.00015, 0.0),
    # Anthropic Claude
    "claude-3-5-haiku": (0.0008, 0.004),
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-3-7-sonnet": (0.003, 0.015),
    "claude-sonnet-4": (0.003, 0.015),
    "claude-opus-4": (0.015, 0.075),
}


def _match(model: str, table: dict[str, tuple[float, float]]) -> tuple[float, float] | None:
    """Exact match, else longest-prefix match (so dated ids resolve and the more
    specific 'gpt-4o-mini' wins over 'gpt-4o')."""
    if model in table:
        return table[model]
    for known in sorted(table, key=len, reverse=True):
        if known and model.startswith(known):
            return table[known]
    return None


def price_for(model: str | None) -> tuple[float, float] | None:
    if not model:
        return None
    # Primary: the live LiteLLM pricing map (cached). Fallback: the built-in table.
    return _match(model, _load_litellm_prices()) or _match(model, _PRICES)


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
