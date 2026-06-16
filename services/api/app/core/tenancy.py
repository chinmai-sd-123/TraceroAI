"""Multi-tenant-lite helpers: resolve an API key to a project_id.

Keeps tenancy out of the request handlers — the route reads the Authorization
header, asks here for the project, and stamps the trace with it (server-trusted).
No users/projects tables yet; the key->project map lives in settings.
"""

from __future__ import annotations

from app.core.config import get_settings


def project_for_api_key(authorization: str | None) -> str | None:
    """Resolve a Bearer API key to its project_id, or None if unknown/absent.

    None means "unauthenticated" — the caller keeps the client-provided project.
    """
    if not authorization:
        return None

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return None

    return get_settings().project_api_keys.get(token)
