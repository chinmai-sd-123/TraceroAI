"""Remove sensitive data from traces before they leave your application.

Pass a function as redact= to TraceroClient or AsyncTraceroClient. It receives
a copy of each trace (a dict, as sent to POST /v1/traces) and returns the trace
to send, or None to drop it. It runs before the trace is queued, so the
unredacted text never waits in the send queue.

    from traceroai import TraceroClient
    from traceroai.redaction import mask_emails, redact_strings

    client = TraceroClient(redact=redact_strings(mask_emails))

If the function raises, the trace is dropped, never sent unredacted, and the
failure is counted in client.redaction_failures. The trace id can't be
changed: the one the client generated is kept, so retries stay safe.
"""

from __future__ import annotations

import copy
import logging
import re
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("traceroai")

Redactor = Callable[[dict[str, Any]], "dict[str, Any] | None"]

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Structural fields that hold no user text; redact_strings leaves them alone so
# a redaction can't break the trace (an id, a timestamp, a model name).
_STRUCTURAL_KEYS = frozenset(
    {"trace_id", "schema_version", "timestamp", "status", "project", "model", "provider", "version",
     "template_name", "strategy", "chunk_id", "document_id", "rank"}
)


def mask_emails(text: str) -> str:
    """Replace email addresses with "[email]"."""
    return EMAIL.sub("[email]", text)


def redact_strings(transform: Callable[[str], str]) -> Redactor:
    """A redactor that applies transform to every string in the trace that can
    hold user text: the question, the retrieved chunks, the prompt, the answer
    and metadata. Ids, timestamps, model names and the project are kept."""

    def walk(value: Any, key: str | None = None) -> Any:
        if key in _STRUCTURAL_KEYS:
            return value
        if isinstance(value, str):
            return transform(value)
        if isinstance(value, dict):
            return {k: walk(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [walk(item, key) for item in value]
        return value

    def redactor(trace: dict[str, Any]) -> dict[str, Any]:
        return walk(trace)

    return redactor


class RedactionError(Exception):
    """The redact function raised, or returned something other than a dict."""


class Redaction:
    """Runs a redactor safely and counts its failures (internal)."""

    def __init__(self, redactor: Redactor) -> None:
        self.redactor = redactor
        self.failures = 0

    def apply(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """The trace to send, or None to drop it. Raises RedactionError when the
        redactor fails; callers that must never raise use apply_quietly."""
        try:
            result = self.redactor(copy.deepcopy(payload))
        except Exception as exc:  # noqa: BLE001 - anything the user's function raises
            raise RedactionError(f"redact raised {type(exc).__name__}: {exc}") from exc
        if result is None:
            return None
        if not isinstance(result, dict):
            raise RedactionError(f"redact returned {type(result).__name__}, not a dict or None")
        result["trace_id"] = payload["trace_id"]  # the id stays the client's, for safe retries
        return result

    def apply_quietly(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """apply, but a failure drops the trace instead of raising."""
        try:
            return self.apply(payload)
        except RedactionError as exc:
            self.failures += 1
            if self.failures == 1 or self.failures % 100 == 0:
                logger.warning(
                    "TraceroAI: trace %s dropped, not sent unredacted (%s); %d dropped so far",
                    payload.get("trace_id"),
                    exc,
                    self.failures,
                )
            return None
