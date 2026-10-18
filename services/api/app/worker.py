"""Deep-eval worker: `python -m app.worker`.

Consumes the deep-eval Redis Stream as part of a consumer group (see
app/services/deep_eval_queue.py for why a stream):

- New jobs are read with XREADGROUP and acknowledged (XACK) only after the
  evaluation is written, so a crash mid-job loses nothing.
- A failed job is left pending. Once it has been idle for VISIBILITY_TIMEOUT_MS,
  any worker reclaims it with XAUTOCLAIM and tries again. The idle time doubles
  as the retry backoff.
- After MAX_DELIVERIES attempts the job is moved to the dead-letter stream. On
  that last attempt a transient judge error (e.g. a rate limit) is recorded as
  an "error" deep result instead of being retried again.

Several workers can run side by side; each needs a unique consumer name.
"""

from __future__ import annotations

import logging
import os
import signal
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import redis

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.deep_eval_queue import DEAD_LETTER_STREAM, GROUP, LEGACY_LIST, STREAM
from app.services.deep_evaluation import TransientEvaluationError, run_deep_evaluation

logger = logging.getLogger("traceroai.worker")

MAX_DELIVERIES = 5
VISIBILITY_TIMEOUT_MS = 60_000
# Must stay below the Redis client's socket read timeout, or an idle block
# looks like a dead connection.
BLOCK_MS = 2_000
RECLAIM_INTERVAL_SECONDS = 15.0

# (trace_id, retry_transient=...) -> None
Handler = Callable[..., None]


@dataclass(frozen=True)
class Job:
    message_id: str
    trace_id: str
    deliveries: int


class DeepEvalWorker:
    def __init__(
        self,
        client: redis.Redis,
        consumer: str,
        handler: Handler = run_deep_evaluation,
        *,
        max_deliveries: int = MAX_DELIVERIES,
        visibility_timeout_ms: int = VISIBILITY_TIMEOUT_MS,
        block_ms: int = BLOCK_MS,
    ) -> None:
        self.client = client
        self.consumer = consumer
        self.handler = handler
        self.max_deliveries = max_deliveries
        self.visibility_timeout_ms = visibility_timeout_ms
        self.block_ms = block_ms

    # --- setup ---

    def ensure_group(self) -> None:
        try:
            self.client.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
        except redis.exceptions.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):  # the group already exists: fine
                raise

    def migrate_legacy_list(self) -> int:
        """Move jobs left on the old list queue onto the stream."""
        moved = 0
        while (trace_id := self.client.rpop(LEGACY_LIST)) is not None:
            self.client.xadd(STREAM, {"trace_id": trace_id})
            moved += 1
        if moved:
            logger.info("Moved %d job(s) from the legacy list queue to the stream", moved)
        return moved

    # --- reading ---

    def read_new(self, count: int = 1) -> list[Job]:
        response = self.client.xreadgroup(
            GROUP, self.consumer, {STREAM: ">"}, count=count, block=self.block_ms
        )
        jobs = []
        for _stream, messages in response or []:
            for message_id, fields in messages:
                jobs.append(Job(message_id, fields.get("trace_id", ""), deliveries=1))
        return jobs

    def reclaim_stale(self, count: int = 10) -> list[Job]:
        """Take over jobs that another (likely dead) worker, or an earlier failed
        attempt, left pending longer than the visibility timeout."""
        _next_id, messages, *_deleted = self.client.xautoclaim(
            STREAM, GROUP, self.consumer, min_idle_time=self.visibility_timeout_ms,
            start_id="0-0", count=count,
        )
        jobs = []
        for message_id, fields in messages:
            # A job trimmed from the stream before it was processed: Redis 7 drops
            # it from the pending list itself; older versions return (None, None).
            if message_id is None:
                continue
            if not fields:
                self.client.xack(STREAM, GROUP, message_id)
                continue
            jobs.append(
                Job(message_id, fields.get("trace_id", ""), self._deliveries(message_id))
            )
        return jobs

    def _deliveries(self, message_id: str) -> int:
        entries = self.client.xpending_range(
            STREAM, GROUP, min=message_id, max=message_id, count=1
        )
        return int(entries[0]["times_delivered"]) if entries else 1

    # --- processing ---

    def handle(self, job: Job) -> str:
        """Process one job. Returns the outcome: acked, retry, or dead_lettered."""
        try:
            trace_id = UUID(job.trace_id)
        except ValueError:
            # A malformed job will never succeed: don't burn retries on it.
            return self._dead_letter(job, f"invalid trace_id {job.trace_id!r}")

        final_attempt = job.deliveries >= self.max_deliveries
        try:
            self.handler(trace_id, retry_transient=not final_attempt)
        except TransientEvaluationError as exc:
            logger.warning(
                "Transient judge error for %s (attempt %d/%d), will retry: %s",
                trace_id, job.deliveries, self.max_deliveries, exc,
            )
            return "retry"
        except Exception as exc:
            if final_attempt:
                return self._dead_letter(job, f"{type(exc).__name__}: {exc}")
            logger.exception(
                "Deep eval failed for %s (attempt %d/%d), will retry",
                trace_id, job.deliveries, self.max_deliveries,
            )
            return "retry"

        self.client.xack(STREAM, GROUP, job.message_id)
        logger.info("Evaluated %s", trace_id)
        return "acked"

    def _dead_letter(self, job: Job, error: str) -> str:
        self.client.xadd(
            DEAD_LETTER_STREAM,
            {
                "trace_id": job.trace_id,
                "message_id": job.message_id,
                "deliveries": str(job.deliveries),
                "error": error[:1000],
                "failed_at": datetime.now(UTC).isoformat(),
            },
        )
        self.client.xack(STREAM, GROUP, job.message_id)
        logger.error("Dead-lettered job %s (trace %s): %s", job.message_id, job.trace_id, error)
        return "dead_lettered"

    # --- loop ---

    def run(self, stop: threading.Event) -> None:
        self.ensure_group()
        self.migrate_legacy_list()
        logger.info("Worker %s consuming %s (group %s)", self.consumer, STREAM, GROUP)

        last_reclaim = 0.0
        while not stop.is_set():
            try:
                jobs: list[Job] = []
                if time.monotonic() - last_reclaim >= RECLAIM_INTERVAL_SECONDS:
                    jobs = self.reclaim_stale()
                    last_reclaim = time.monotonic()
                if not jobs:
                    jobs = self.read_new()
                for job in jobs:
                    self.handle(job)
            except redis.exceptions.RedisError:
                logger.exception("Redis error; retrying in 1s")
                stop.wait(1)
        logger.info("Worker %s stopped", self.consumer)


def main() -> None:
    settings = get_settings()
    configure_logging(
        json_logs=settings.app_env in ("staging", "production"), level=settings.log_level
    )
    if not settings.redis_url:
        raise SystemExit("TRACEROAI_REDIS_URL is not set; the worker needs Redis.")

    client = redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=BLOCK_MS / 1000 + 8,  # comfortably above the blocking read
        health_check_interval=30,
    )
    consumer = f"{socket.gethostname()}-{os.getpid()}"

    # Finish the current job, then exit. An interrupted job stays pending and is
    # reclaimed by the next worker.
    stop = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stop.set())

    DeepEvalWorker(client, consumer).run(stop)


if __name__ == "__main__":
    main()
