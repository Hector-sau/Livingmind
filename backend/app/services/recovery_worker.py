"""Conservative receipt recovery: no submit(), no restart of stopped services.

Only the shared, persistent HTTP gateway deployment may run this worker. A process-
local virtual gateway would provide another, unrelated set of device receipts.
"""
import logging
import signal
import threading

from app import config
from app.adapters.http_gateway import HttpDeviceAdapter, HttpDeviceGateway
from app.clock import utc_now
from app.harness.reconciliation import resolve_receipt
from app.observability.events import record
from app.repositories.sql_store import SqlStore


class RecoveryWorker:
    def __init__(self, store, gateway_for, clock=utc_now, *, max_attempts=5, max_age_s=900, lease_s=30):
        if max_attempts < 1 or max_age_s <= 0 or lease_s <= 0:
            raise ValueError("Recovery limits must be positive")
        self.store, self.gateway_for, self.clock = store, gateway_for, clock
        self.limits = dict(max_attempts=max_attempts, max_age_s=max_age_s)
        self.lease_s = lease_s

    def run_once(self, batch_size=10):
        # Do not treat unowned rows from the legacy single-process mode as dead.
        self.store.startup_reconcile(include_legacy=False)
        checked = resolved_count = 0
        for _ in range(batch_size):
            claimed = self.store.claim_action_recovery(self.clock(), lease_s=self.lease_s, **self.limits)
            if claimed is None:
                break
            execution, token = claimed
            checked += 1
            try:
                resolved = resolve_receipt(execution, self.gateway_for(execution.space_id), self.clock)
                if resolved:
                    current = self.store.resolve_unknown_action(*resolved, recovery_token=token)
                    resolved_count += int(current is not None and current.status != "unknown")
            finally:
                self.store.finish_action_recovery(execution.action_id, token, self.clock(), **self.limits)
            record("action.recovery.checked", actionId=execution.action_id, serviceId=execution.service_id,
                   planId=execution.plan_id, attempt=execution.recovery_attempts)
        return {"checked": checked, "resolved": resolved_count}


def main():
    if not config.DATABASE_URL or not config.GATEWAY_URL or not config.GATEWAY_TOKEN:
        raise RuntimeError("Recovery requires PostgreSQL and the persistent HTTP gateway; not the in-memory demo")
    store, adapters = SqlStore(), {}

    def gateway_for(space_id):
        if space_id not in adapters:
            adapters[space_id] = HttpDeviceAdapter(space_id, config.GATEWAY_URL, config.GATEWAY_TOKEN,
                                                  store.epoch, config.GATEWAY_TIMEOUT_S)
        return HttpDeviceGateway(adapters[space_id])

    worker = RecoveryWorker(store, gateway_for, lease_s=max(30, config.GATEWAY_TIMEOUT_S * 4 + 5))
    stopped = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopped.set())
    try:
        while not stopped.is_set():
            try:
                worker.run_once()
            except Exception as exc:
                # Keep DB outages visible without logging credentials/SQL parameters.
                logging.error("Recovery pass failed (%s); no device command was retried", type(exc).__name__)
            stopped.wait(2)
    finally:
        for adapter in adapters.values():
            adapter.close()


if __name__ == "__main__":
    main()
