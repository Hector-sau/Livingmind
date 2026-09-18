"""Event cooldown: a Redis key with a TTL in front of the authoritative service row."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional

from app.cache.client import _optional, redis_client
from app.cache.keys import event_cooldown


class Cooldown:
    def __init__(self, seconds: float):
        self.seconds = seconds

    def remaining(self, service_id: str, now: Optional[datetime] = None) -> Optional[int]:
        """Seconds left, 0/None when not cooling down or when Redis is unavailable."""
        client = redis_client()
        if client is None or self.seconds <= 0:
            return None
        key = event_cooldown(service_id)
        cached = _optional(lambda: (client.get(key), client.ttl(key)))
        if cached is None:
            return None
        value, ttl = cached
        if ttl is None or ttl < 0:
            return None
        if now is not None and value not in (None, "1"):
            try:
                clock_left = math.ceil(float(value) - now.timestamp())
            except (TypeError, ValueError):
                clock_left = ttl
            if clock_left <= 0:
                self.clear(service_id)
                return None
            return min(ttl, clock_left)
        return ttl

    def start(self, service_id: str, now: Optional[datetime] = None) -> None:
        client = redis_client()
        if client is None or self.seconds <= 0:
            return
        value = "1" if now is None else str((now + timedelta(seconds=self.seconds)).timestamp())
        _optional(lambda: client.set(event_cooldown(service_id), value, ex=max(1, math.ceil(self.seconds))))

    def clear(self, service_id: str) -> None:
        client = redis_client()
        if client is None:
            return
        _optional(lambda: client.delete(event_cooldown(service_id)))
