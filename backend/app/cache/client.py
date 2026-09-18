"""Connection handling. Redis is optional: no URL means the demo behaves exactly as before."""

from __future__ import annotations

from typing import Optional

from app import config

_client = None
_pool = None


def cache_configured() -> bool:
    return bool(config.REDIS_URL)


def redis_client():
    """A shared pooled client, or None when Redis is not configured or not reachable."""
    global _client, _pool
    if not config.REDIS_URL:
        return None
    if _client is None:
        import redis

        _pool = redis.ConnectionPool.from_url(
            config.REDIS_URL, socket_timeout=0.5, socket_connect_timeout=0.5, decode_responses=True
        )
        _client = redis.Redis(connection_pool=_pool)
    return _client


def reset_client() -> None:
    """Tests only: forget the cached client so a new URL (or a stopped server) takes effect."""
    global _client, _pool
    if _pool is not None:
        _pool.disconnect()
    _client, _pool = None, None


def available() -> bool:
    """True only if a ping succeeds right now. Never raises: callers fall back to PostgreSQL."""
    client = redis_client()
    if client is None:
        return False
    try:
        return bool(client.ping())
    except Exception:
        return False


def _optional(call, default=None):
    """Run a Redis call, returning ``default`` if Redis is down. Used by every cache helper."""
    try:
        return call()
    except Exception:
        return default
