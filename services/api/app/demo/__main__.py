"""Load (or remove) the demo data: `python -m app.demo`.

    python -m app.demo                          # against http://localhost:8000
    python -m app.demo --api http://api:8000    # from inside Docker Compose
    python -m app.demo --remove                 # delete the demo project

Needs the API to be running, and the database (TRACEROAI_DATABASE_URL) to spread
the demo traces over the past week. When the API requires keys, pass an admin key
with --key or TRACEROAI_API_KEY.
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx

from app.db.session import SessionLocal
from app.demo import DEMO_PROJECT, remove, seed, spread_over_last_week


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.demo", description="Load the TraceroAI demo data.")
    parser.add_argument("--api", default=os.environ.get("TRACEROAI_API_URL", "http://localhost:8000"))
    parser.add_argument("--key", default=os.environ.get("TRACEROAI_API_KEY"), help="API key, if the API requires one")
    parser.add_argument("--remove", action="store_true", help="delete the demo project instead")
    parser.add_argument("--wait", type=float, default=120.0, help="seconds to wait for diagnoses")
    args = parser.parse_args()

    if args.remove:
        with SessionLocal() as db:
            traces, runs = remove(db)
        print(f"Removed the {DEMO_PROJECT} project: {traces} traces, {runs} eval runs.")
        return 0

    headers = {"Authorization": f"Bearer {args.key}"} if args.key else {}
    with httpx.Client(base_url=args.api.rstrip("/"), headers=headers, timeout=30.0) as client:
        try:
            client.get("/health").raise_for_status()
        except httpx.HTTPError as exc:
            print(f"Can't reach the API at {args.api} ({exc}). Start it first.", file=sys.stderr)
            return 1
        result = seed(client, wait_seconds=args.wait)

    with SessionLocal() as db:
        moved = spread_over_last_week(db)

    print(
        f"Demo data in project '{DEMO_PROJECT}': {result.sent} traces sent, {result.already_there} already there, "
        f"{result.diagnosed} diagnosed; experiment {result.experiment}; {moved} traces spread over the past week."
    )
    if result.experiment.startswith("failed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
