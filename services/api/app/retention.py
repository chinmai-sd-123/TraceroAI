"""Delete traces past the retention period: `python -m app.retention`.

Uses TRACEROAI_TRACE_RETENTION_DAYS, or --days. The worker does this hourly
when the setting is present; run this from cron where there's no worker.
"""

from __future__ import annotations

import argparse

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.trace_repository import TraceRepository


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.retention")
    parser.add_argument("--days", type=int, help="override TRACEROAI_TRACE_RETENTION_DAYS")
    args = parser.parse_args(argv)

    days = args.days or get_settings().trace_retention_days
    if not days or days < 1:
        print("No retention period: set TRACEROAI_TRACE_RETENTION_DAYS or pass --days.")
        return 1
    with SessionLocal() as db:
        deleted = TraceRepository(db).purge_older_than(days)
    print(f"Deleted {deleted} trace(s) older than {days} day(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
