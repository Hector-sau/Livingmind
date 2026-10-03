"""Read-only gateway reconciliation: a lost reply is never retried as a write.

A matching action receipt is required. Current device state alone cannot prove which
command caused it, so it must not be used to turn unknown into completed.
"""

from app.adapters.protocol import DeviceGateway
from app.clock import Clock
from app.contracts import ActionExecution, ActionResult


def resolve_receipt(execution: ActionExecution, gateway: DeviceGateway, clock: Clock):
    if execution.status != "unknown":
        return None
    try:
        receipt = gateway.query(execution.action_id)
    except OSError:
        return None
    if receipt is None or receipt.action_id != execution.action_id or receipt.status in ("unknown", "accepted"):
        return None
    observed = receipt.observed_value
    if receipt.status == "completed":
        # Require action-specific evidence with a timestamp, not just equal values.
        if receipt.observed_at is None or receipt.observed_at.tzinfo is None:
            return None
        if receipt.observed_at < execution.requested_at:
            return None
        if observed is None:
            return None
        matched = float(observed) == float(execution.requested_value)
        status, outcome = ("completed", "succeeded") if matched else ("failed", "failed")
        kind = None if matched else "readback_mismatch"
        detail = None if matched else "回执已核对，但回读值与目标不一致"
    elif receipt.status in ("failed", "rejected"):
        status = outcome = receipt.status
        kind, detail = receipt.error_kind, receipt.detail or "网关确认未完成"
    else:
        return None
    resolved = execution.model_copy(update={
        "status": status, "completed_at": clock(), "observed_value": observed,
        "observed_at": receipt.observed_at, "error_kind": kind, "error_detail": detail,
    })
    result = ActionResult(action_id=execution.action_id, device=execution.device, command=execution.command,
                          value=execution.requested_value, outcome=outcome, reason=detail, observed_value=observed)
    return resolved, result
