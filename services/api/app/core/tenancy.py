"""Multi-tenant-lite helpers: resolve an API key to a project_id.

Keeps tenancy out of the request handlers — routes declare a dependency
(`write_project` / `optional_project`) and receive the authenticated project,
which they stamp onto what they store (server-trusted, never client-claimed).
No users/projects tables yet; the key->project map lives in settings.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from app.core.config import get_settings


def project_for_api_key(authorization: str | None) -> str | None:
    """Resolve a Bearer API key to its project_id, or None if unknown/absent."""
    if not authorization:
        return None

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return None

    return get_settings().project_api_keys.get(token)


def api_key_required() -> bool:
    """Whether writes must carry a valid key.

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


def optional_project(authorization: str | None = Header(default=None)) -> str | None:
    """The project for the request's API key, or None if no key was sent.

    A key that IS sent but isn't recognized is always rejected: silently ignoring
    it would attribute the data to whatever project the client claims.
    """
    if not authorization:
        return None
    project_id = project_for_api_key(authorization)
    if project_id is None:
        raise _unauthorized("Invalid API key.")
    return project_id


def write_project(project_id: str | None = Depends(optional_project)) -> str | None:
    """Dependency for write endpoints: the authenticated project, or None when
    unauthenticated writes are allowed (development). Raises 401 otherwise."""
    if project_id is None and api_key_required():
        raise _unauthorized("A valid project API key is required.")
    return project_id
