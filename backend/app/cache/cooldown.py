"""Event cooldown: a Redis key with a TTL in front of the authoritative service row."""

from __future__ import annotations

from typing import Optional

from app.cache.client import _optional, redis_client
from app.cache.keys import event_cooldown


class Cooldown:
    def __init__(self, seconds: float):
        self.seconds = seconds

    def remaining(self, service_id: str) -> Optional[int]:
        """Seconds left, 0/None when not cooling down or when Redis is unavailable."""
        client = redis_client()
        if client is None or self.seconds <= 0:
            return None
        ttl = _optional(lambda: client.ttl(event_cooldown(service_id)))
        if ttl is None or ttl < 0:
            return None
        return ttl

    def start(self, service_id: str) -> None:
        client = redis_client()
        if client is None or self.seconds <= 0:
            return
        _optional(lambda: client.set(event_cooldown(service_id), "1", ex=max(1, int(self.seconds))))

    def clear(self, service_id: str) -> None:
        client = redis_client()
        if client is None:
            return
        _optional(lambda: client.delete(event_cooldown(service_id)))
