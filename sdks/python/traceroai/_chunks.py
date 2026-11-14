"""Turn whatever a retriever returns into chunks the API accepts.

The API needs `rank` (from 1), `chunk_id` and non-empty `text` on every chunk,
and rejects the whole trace if one is missing, so the trace was lost over a
detail. Here, missing ranks and ids are filled in from the position, LangChain
`Document` objects (anything with `page_content`) are converted, and chunks
with no text are left out.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("traceroai")

# Metadata keys LangChain loaders commonly set, mapped to TraceroAI fields.
_METADATA_FIELDS = {
    "id": "chunk_id",
    "chunk_id": "chunk_id",
    "document_id": "document_id",
    "doc_id": "document_id",
    "title": "document_title",
    "document_title": "document_title",
    "source": "source",
    "section": "section",
    "score": "final_score",
}


def _as_dict(chunk: Any) -> dict[str, Any]:
    if isinstance(chunk, dict):
        return dict(chunk)
    if hasattr(chunk, "page_content"):  # langchain_core.documents.Document
        converted: dict[str, Any] = {"text": chunk.page_content}
        metadata = getattr(chunk, "metadata", None) or {}
        for key, field in _METADATA_FIELDS.items():
            if key in metadata and field not in converted:
                converted[field] = metadata[key]
        if getattr(chunk, "id", None) and "chunk_id" not in converted:
            converted["chunk_id"] = chunk.id
        return converted
    if isinstance(chunk, str):
        return {"text": chunk}
    return {"text": str(chunk)}


def normalize_chunks(chunks: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    skipped = 0
    for chunk in chunks or []:
        item = _as_dict(chunk)
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            skipped += 1
            continue
        position = len(normalized) + 1
        if not isinstance(item.get("rank"), int) or item["rank"] < 1:
            item["rank"] = position
        if not item.get("chunk_id"):
            item["chunk_id"] = f"chunk-{position}"
        item["chunk_id"] = str(item["chunk_id"])
        normalized.append(item)
    if skipped:
        logger.debug("TraceroAI: left out %d chunk(s) without text", skipped)
    return normalized
