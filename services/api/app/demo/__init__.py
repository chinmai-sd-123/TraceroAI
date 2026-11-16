"""Demo data for a first run: `python -m app.demo`.

Replays recorded runs (recorded_runs.json: real answers from the recovery-agent
example) through the API, so a fresh install has something to look at. The
server evaluates and diagnoses them exactly as it would any trace: with a
provider key the LLM judge decides; without one, the diagnoses are estimates.

Everything lands in the `demo` project. Seeding again changes nothing (trace and
eval-run ids are fixed), and `--remove` deletes it all.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

DEMO_PROJECT = "demo"
RECORDED = Path(__file__).with_name("recorded_runs.json")


def load_recorded() -> dict[str, Any]:
    return json.loads(RECORDED.read_text(encoding="utf-8"))


@dataclass
class SeedResult:
    sent: int
    already_there: int
    diagnosed: int
    experiment: str  # "sent", "already there" or "failed: ..."


def seed(client: httpx.Client, *, wait_seconds: float = 120.0) -> SeedResult:
    """Send the recorded traces and the experiment through the API.

    `client` has the API's base URL (and key, if one is required). Waits until
    every trace has left the "pending" diagnosis or `wait_seconds` passes.
    """
    recorded = load_recorded()
    sent = already = 0
    ids = []
    for trace in recorded["traces"]:
        exists = client.get(f"/v1/traces/{trace['trace_id']}").status_code == 200
        response = client.post("/v1/traces", json=trace)
        response.raise_for_status()
        ids.append(trace["trace_id"])
        already += exists
        sent += not exists

    response = client.post("/v1/eval-runs", json=recorded["experiment"])
    if response.status_code == 409:
        experiment = "already there"
    elif response.is_success:
        experiment = "sent"
    else:
        experiment = f"failed: HTTP {response.status_code} {response.text[:200]}"

    deadline = time.monotonic() + wait_seconds
    diagnosed: set[str] = set()
    while True:
        for trace_id in ids:
            if trace_id in diagnosed:
                continue
            got = client.get(f"/v1/traces/{trace_id}")
            if got.is_success and got.json().get("diagnosis", {}).get("label") != "pending":
                diagnosed.add(trace_id)
        if len(diagnosed) == len(ids) or time.monotonic() > deadline:
            break
        time.sleep(1)
    return SeedResult(sent=sent, already_there=already, diagnosed=len(diagnosed), experiment=experiment)


def spread_over_last_week(db: Session, *, now: datetime | None = None) -> int:
    """Give the demo traces arrival times across the past seven days.

    The database stamps a trace when it arrives, so a fresh seed would put every
    demo trace in the same minute and the overview's charts would be one bar.
    Recovery attempts stay together, a minute apart, in their original order.
    Only the demo project is touched. Returns the number of traces moved.
    """
    now = now or datetime.now(UTC)
    recorded = load_recorded()["traces"]
    # Group attempts of one recovery run; every other trace is its own group.
    groups: list[list[str]] = []
    by_run: dict[str, list[str]] = {}
    for trace in recorded:
        run_id = (trace.get("metadata") or {}).get("recovery_run_id")
        if run_id is None:
            groups.append([trace["trace_id"]])
        elif run_id in by_run:
            by_run[run_id].append(trace["trace_id"])
        else:
            by_run[run_id] = [trace["trace_id"]]
            groups.append(by_run[run_id])

    moved = 0
    # From six and a half days ago (inside the overview's "7d" range even after
    # the minute jitter below) to an hour ago.
    first, last = now - timedelta(days=6, hours=12), now - timedelta(hours=1)
    for index, group in enumerate(groups):
        start = first + (last - first) * (index / max(1, len(groups) - 1))
        start -= timedelta(minutes=(index * 37) % 50)
        for offset, trace_id in enumerate(group):
            at = start + timedelta(minutes=offset)
            # Both clocks: lists sort by created_at and show the trace's own timestamp.
            result = db.execute(
                text(
                    "UPDATE traces SET created_at = :at, "
                    "payload = jsonb_set(payload, '{timestamp}', to_jsonb(CAST(:iso AS text))) "
                    "WHERE trace_id = :id AND project_id = :project"
                ),
                {"at": at, "iso": at.isoformat(), "id": trace_id, "project": DEMO_PROJECT},
            )
            moved += result.rowcount or 0  # type: ignore[attr-defined]
    db.commit()
    return moved


def remove(db: Session) -> tuple[int, int]:
    """Delete the demo project's traces and eval runs. Returns (traces, eval runs)."""
    traces = db.execute(text("DELETE FROM traces WHERE project_id = :p"), {"p": DEMO_PROJECT})
    runs = db.execute(text("DELETE FROM eval_runs WHERE project_id = :p"), {"p": DEMO_PROJECT})
    db.commit()
    return traces.rowcount or 0, runs.rowcount or 0  # type: ignore[attr-defined]
