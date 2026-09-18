"""Space lock: shortens the window where two API instances drive the same devices.

It is NOT the safety guarantee. The guarantees are in PostgreSQL (one active service per
space, a night step claimed once) and in the executor guard, which re-checks before every
write. If Redis is down, the lock silently becomes a no-op and those checks still hold.
"""

from __future__ import annotations

import uuid
from typing import Optional

from app.cache.client import _optional, redis_client
from app.cache.keys import EXECUTOR_LOCK_TTL_S, space_executor_lock

# Release only our own lock: a lock that already expired may belong to someone else by now.
_RELEASE = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


def lock_token() -> str:
    return uuid.uuid4().hex


class SpaceLock:
    """Context manager. ``acquired`` says whether we really hold it (False when Redis is off)."""

    def __init__(self, space_id: str, ttl_s: int = EXECUTOR_LOCK_TTL_S):
        self.key = space_executor_lock(space_id)
        self.ttl_s = ttl_s
        self.token = lock_token()
        self.acquired = False
        self.degraded = False

    def __enter__(self) -> "SpaceLock":
        client = redis_client()
        if client is None:
            self.degraded = True
            return self
        result = _optional(lambda: client.set(self.key, self.token, nx=True, ex=self.ttl_s), default="down")
        if result == "down":
            self.degraded = True  # Redis unreachable: fall through to the database path
        else:
            self.acquired = bool(result)
        return self

    def __exit__(self, *exc) -> None:
        if not self.acquired:
            return
        client = redis_client()
        if client is not None:
            _optional(lambda: client.eval(_RELEASE, 1, self.key, self.token))
        self.acquired = False

    @property
    def blocked(self) -> bool:
        """True only when Redis is up and someone else holds the lock."""
        return not self.acquired and not self.degraded
