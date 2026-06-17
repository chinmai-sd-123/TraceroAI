"""Hosted embedding client for semantic similarity in the quick evaluators.

Reuses the judge's provider config (openai_api_key + judge_base_url), so it works
with OpenAI or any OpenAI-compatible endpoint (e.g. Gemini's). Kept separate from
the LLM judge because embeddings are a different, much cheaper call used on the
synchronous ingest path.
"""

from __future__ import annotations
import math
from openai import OpenAI
from app.core.config import Settings, get_settings


class EmbeddingClient:
    """Encodes text to vectors via a hosted embeddings API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = OpenAI(
            api_key=self._settings.openai_api_key,
            base_url=self._settings.judge_base_url,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts in one request. Order matches the input."""
        response = self._client.embeddings.create(
            model=self._settings.embedding_model,
            input=texts,
        )
        return [item.embedding for item in response.data]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two vectors, clamped to [0, 1]."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    similarity = dot / (norm_a * norm_b)
    return max(0.0, min(1.0, similarity))
