"""Bring the database schema up to date: `python -m app.db.init_db`.

Runs the Alembic migrations to head; the same as `alembic upgrade head` from
services/api. Safe to run repeatedly, and safe on a database that was set up
before migrations existed (the baseline only creates missing tables).
"""

from pathlib import Path

from alembic import command
from alembic.config import Config

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def init_db() -> None:
    config = Config(str(ALEMBIC_INI))
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")


if __name__ == "__main__":
    init_db()
    print("Database schema is up to date.")
