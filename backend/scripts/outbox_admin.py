"""Inspect/retry retained outbox dead letters; requires DB access, not exposed as a public API.

Examples (use a disposable or explicitly authorised database):
    python scripts/outbox_admin.py --list
    python scripts/outbox_admin.py --retry EVENT_ID
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.events.outbox import dead_letters, retry_dead_letter  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true")
    group.add_argument("--retry", metavar="EVENT_ID")
    args = parser.parse_args()
    if args.list:
        for event in dead_letters():
            print(event.event_id, event.event_type, event.space_id)
        return 0
    retried = retry_dead_letter(args.retry)
    print("requeued" if retried else "not a retryable dead letter")
    return 0 if retried else 1


if __name__ == "__main__":
    raise SystemExit(main())
