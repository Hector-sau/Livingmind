"""Publisher process: moves outbox rows onto the bus, with backoff and no data loss."""

from __future__ import annotations

import logging
import time
from typing import Optional

from app.events.outbox import dead_letters, publish_pending
from app.events.publisher import PostgresQueuePublisher

log = logging.getLogger("livingmind.outbox")


def run(poll_seconds: float = 1.0, iterations: Optional[int] = None) -> None:
    publisher = PostgresQueuePublisher()
    backoff = poll_seconds
    count = 0
    while iterations is None or count < iterations:
        result = publish_pending(publisher)
        if result["failed"]:
            backoff = min(backoff * 2, 30.0)  # the bus is down: slow down, keep the rows
            log.warning("outbox publish failed: %s; retrying in %.1fs", result, backoff)
        else:
            backoff = poll_seconds
        stuck = dead_letters()
        if stuck:
            log.error("%d outbox events exceeded the retry limit and need attention", len(stuck))
        count += 1
        time.sleep(backoff)


if __name__ == "__main__":  # pragma: no cover - entry point for the compose service
    logging.basicConfig(level=logging.INFO)
    run()
