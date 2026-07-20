"""
Redis key helpers for a shared Redis instance.

Every key this service writes must start with Settings.redis_prefix
(e.g. ``renderpop_server_``) so we never collide with sibling projects.
"""

from app.core.config import get_settings


def redis_key(*parts: str | int) -> str:
    """
    Build a namespaced Redis key.

    Example:
        redis_key("session", session_id) -> "renderpop_server_session:<id>"
        redis_key("lock", "job", job_id) -> "renderpop_server_lock:job:<id>"
    """
    prefix = get_settings().redis_prefix
    body = ":".join(str(p) for p in parts if p is not None and p != "")
    return f"{prefix}{body}"
