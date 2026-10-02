"""Small structured events for timing and correlation; no prompts or personal values."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.observability.context import current_request_id

logger = logging.getLogger("livingmind.events")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


def record(event: str, **fields) -> None:
    logger.info(json.dumps({
        "event": event,
        "at": datetime.now(timezone.utc).isoformat(),
        "requestId": current_request_id(),
        **fields,
    }, ensure_ascii=False))
