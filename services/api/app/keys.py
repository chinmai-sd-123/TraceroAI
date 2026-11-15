"""Manage API keys: `python -m app.keys`.

    python -m app.keys create --project my-app --name "my-app production"
    python -m app.keys create --admin --name "dashboard"
    python -m app.keys list
    python -m app.keys revoke trk_AbCdEfGh     # a key's prefix or id

A new key is printed once; only its hash is stored.
"""

from __future__ import annotations

import argparse
import sys

from app.db.session import SessionLocal
from app.services import api_keys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.keys", description="Manage API keys.")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="create a key and print it once")
    scope = create.add_mutually_exclusive_group(required=True)
    scope.add_argument("--project", help="the project this key writes to and reads")
    scope.add_argument("--admin", action="store_true", help="a key that reads every project")
    create.add_argument("--name", required=True, help="what the key is for")

    commands.add_parser("list", help="list keys (never the keys themselves)")

    revoke = commands.add_parser("revoke", help="revoke a key by id or prefix")
    revoke.add_argument("reference")

    args = parser.parse_args(argv)
    with SessionLocal() as db:
        if args.command == "create":
            key, record = api_keys.create_key(
                db, name=args.name, project_id=args.project, admin=args.admin
            )
            scope_text = "admin (every project)" if args.admin else f"project {args.project}"
            print(f"Created {scope_text} key {record.key_id} ({args.name}):\n\n  {key}\n")
            print("Store it now: it can't be shown again.")
            return 0

        if args.command == "list":
            records = api_keys.list_keys(db)
            if not records:
                print("No keys in the database.")
            for r in records:
                state = f"revoked {r.revoked_at:%Y-%m-%d}" if r.revoked_at else "active"
                used = f"{r.last_used_at:%Y-%m-%d %H:%M}" if r.last_used_at else "never"
                scope_text = "admin" if r.role == "admin" else f"project={r.project_id}"
                print(f"{r.key_id}  {r.prefix}…  {scope_text:<24} {state:<18} "
                      f"last used {used}  {r.name}")
            return 0

        try:
            revoked = api_keys.revoke(db, args.reference)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 1
        if not revoked:
            print(f"No active key matches {args.reference!r}.", file=sys.stderr)
            return 1
        print(f"Revoked {revoked[0].key_id} ({revoked[0].name}).")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
