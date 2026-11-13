"""Who is calling, and which projects they may read or write.

Routes declare a dependency and receive the answer:

- write_project: for writes. The project of the caller's key, which the route
  stamps onto what it stores (server-trusted, never client-claimed).
- read_scope: for reads. The set of projects the caller may see.
- caller: the full picture, for routes that need to tell an admin from an
  anonymous caller (feedback).

Keys come from settings: project keys map to one project each, admin keys see
every project (the dashboard's server uses one). No users/projects tables yet.

When keys are required (staging/production by default), a request without a key
may write nothing and read only the projects listed in public_read_projects.
In development keys are optional and an anonymous caller can read everything.
"""

from __future__ import annotations

import hmac
from collections.abc import Iterable
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status

from app.core.config import get_settings


@dataclass(frozen=True)
class Caller:
    """The resolved identity behind a request.

    project_id is set for a project key. is_admin is set for an admin key.
    Neither is set for a request without a key.
    """

    project_id: str | None = None
    is_admin: bool = False

    @property
    def anonymous(self) -> bool:
        return self.project_id is None and not self.is_admin


@dataclass(frozen=True)
class ReadScope:
    """The projects a caller may read; None means every project."""

    projects: frozenset[str] | None

    def allows(self, project_id: str) -> bool:
        return self.projects is None or project_id in self.projects

    def narrow(self, requested: str | None) -> frozenset[str] | None:
        """The projects to query for an optional ?project_id= filter.

        A filter outside the scope yields an empty set (no rows) rather than an
        error, so the response doesn't reveal whether that project exists.
        """
        if requested is None:
            return self.projects
        return frozenset({requested}) if self.allows(requested) else frozenset()


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    token = authorization.removeprefix("Bearer ").strip()
    return token or None


def _matches_any(token: str, keys: Iterable[str]) -> bool:
    # Compare against every key in constant time, so response timing doesn't
    # reveal how much of a key was right.
    found = False
    for key in keys:
        if hmac.compare_digest(token.encode(), key.encode()):
            found = True
    return found


def project_for_api_key(authorization: str | None) -> str | None:
    """Resolve a Bearer project key to its project_id, or None if unknown/absent."""
    token = _bearer_token(authorization)
    if token is None:
        return None
    for key, project_id in get_settings().project_api_keys.items():
        if hmac.compare_digest(token.encode(), key.encode()):
            return project_id
    return None


def api_key_required() -> bool:
    """Whether callers must present a key.

    An explicit TRACEROAI_REQUIRE_API_KEY wins; otherwise keys are required in
    staging/production and optional in development/testing — so a fresh
    self-hosted deploy is locked down without anyone remembering a flag.
    """
    settings = get_settings()
    if settings.require_api_key is not None:
        return settings.require_api_key
    return settings.app_env in ("staging", "production")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def caller(authorization: str | None = Header(default=None)) -> Caller:
    """Resolve the request's key.

    A key that IS sent but isn't recognized is always rejected: silently
    ignoring it would attribute writes to whatever project the client claims.
    """
    token = _bearer_token(authorization)
    if token is None:
        if authorization:
            raise _unauthorized("Invalid API key.")
        return Caller()
    if _matches_any(token, get_settings().admin_api_keys):
        return Caller(is_admin=True)
    project_id = project_for_api_key(authorization)
    if project_id is None:
        raise _unauthorized("Invalid API key.")
    return Caller(project_id=project_id)


def write_project(who: Caller = Depends(caller)) -> str | None:
    """Dependency for write endpoints: the authenticated project, or None for an
    admin key or (when keys aren't required) no key. Raises 401 otherwise."""
    if who.anonymous and api_key_required():
        raise _unauthorized("A valid project API key is required.")
    return who.project_id


def read_scope(who: Caller = Depends(caller)) -> ReadScope:
    """Dependency for read endpoints: which projects the caller may see."""
    if who.is_admin:
        return ReadScope(None)
    if who.project_id is not None:
        return ReadScope(frozenset({who.project_id}))
    if not api_key_required():
        return ReadScope(None)
    public = get_settings().public_read_projects
    if public:
        return ReadScope(frozenset(public))
    raise _unauthorized("A valid API key is required to read data.")
