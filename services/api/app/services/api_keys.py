"""API keys stored in the database.

A key is "trk_" followed by 43 random URL-safe characters. Only its SHA-256 is
stored, so a database leak doesn't hand out working keys; the key itself is
shown once, when created. Keys in TRACEROAI_PROJECT_API_KEYS and
TRACEROAI_ADMIN_API_KEYS keep working alongside these (useful to bootstrap).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.db.models import ApiKeyRecord

KEY_PREFIX = "trk_"
DISPLAY_PREFIX_LENGTH = 12
# last_used_at is refreshed at most this often, so authenticating a busy key
# doesn't write to the database on every request.
LAST_USED_RESOLUTION = timedelta(minutes=5)


def generate_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(32)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def create_key(
    db: Session, *, name: str, project_id: str | None = None, admin: bool = False
) -> tuple[str, ApiKeyRecord]:
    """Create a key; returns (the key, its record). The key isn't stored."""
    if admin == (project_id is not None):
        raise ValueError("A key is either an admin key or belongs to one project.")
    key = generate_key()
    record = ApiKeyRecord(
        key_id=uuid4(),
        key_hash=hash_key(key),
        prefix=key[:DISPLAY_PREFIX_LENGTH],
        name=name,
        role="admin" if admin else "project",
        project_id=project_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return key, record


def find_active(db: Session, key: str) -> ApiKeyRecord | None:
    """The unrevoked key with this value, if any. A hash lookup on a unique
    index: no timing signal about how much of a key was right."""
    return db.scalar(
        select(ApiKeyRecord).where(
            ApiKeyRecord.key_hash == hash_key(key), ApiKeyRecord.revoked_at.is_(None)
        )
    )


def touch(db: Session, record: ApiKeyRecord) -> None:
    now = datetime.now(UTC)
    if record.last_used_at is None or now - record.last_used_at > LAST_USED_RESOLUTION:
        db.execute(
            update(ApiKeyRecord)
            .where(ApiKeyRecord.key_id == record.key_id)
            .values(last_used_at=now)
        )
        db.commit()


def list_keys(db: Session) -> list[ApiKeyRecord]:
    return list(db.scalars(select(ApiKeyRecord).order_by(ApiKeyRecord.created_at)).all())


def revoke(db: Session, reference: str) -> list[ApiKeyRecord]:
    """Revoke the key whose id or display prefix is `reference`. Revoking is
    immediate: the next request with that key gets a 401."""
    conditions = [ApiKeyRecord.prefix == reference]
    try:
        conditions.append(ApiKeyRecord.key_id == UUID(reference))
    except ValueError:
        pass
    matches = list(
        db.scalars(
            select(ApiKeyRecord).where(or_(*conditions), ApiKeyRecord.revoked_at.is_(None))
        ).all()
    )
    if len(matches) > 1:
        raise ValueError(f"{reference!r} matches {len(matches)} keys; use the key id.")
    for record in matches:
        record.revoked_at = datetime.now(UTC)
    db.commit()
    return matches
