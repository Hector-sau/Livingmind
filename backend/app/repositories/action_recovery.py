"""Short SQL transactions lease receipt queries; never hold row locks across HTTP."""
from datetime import timedelta
import uuid

from sqlalchemy import or_, select

from app.contracts import ActionExecution
from app.db.models import ActionExecutionRow
from app.db.session import session_scope


class ActionRecoveryStore:
    def claim_action_recovery(self, now, *, max_attempts=5, max_age_s=900, lease_s=30):
        with session_scope() as session:
            # Bounded scan; exhausted rows are excluded after the first inspection.
            rows = session.scalars(select(ActionExecutionRow).where(
                ActionExecutionRow.status == "unknown",
                or_(ActionExecutionRow.recovery_until.is_(None), ActionExecutionRow.recovery_until <= now),
                ActionExecutionRow.payload["recovery_exhausted"].as_boolean().is_not(True),
            ).order_by(ActionExecutionRow.updated_at).with_for_update(skip_locked=True).limit(100)).all()
            for row in rows:
                item = ActionExecution.model_validate(row.payload)
                if item.recovery_attempts >= max_attempts or (now - item.requested_at).total_seconds() >= max_age_s:
                    item.recovery_exhausted, item.next_check_at = True, None
                    row.payload = item.model_dump(mode="json")
                    row.recovery_token = row.recovery_until = None
                    continue
                if item.next_check_at is not None and item.next_check_at > now:
                    continue
                row.recovery_token = uuid.uuid4().hex
                row.recovery_until = now + timedelta(seconds=lease_s)
                item.recovery_attempts += 1
                row.payload = item.model_dump(mode="json")
                return item, row.recovery_token
        return None

    def finish_action_recovery(self, action_id, token, now, *, max_attempts=5, max_age_s=900):
        with session_scope() as session:
            row = session.get(ActionExecutionRow, action_id, with_for_update=True)
            if row is None or row.status != "unknown" or row.recovery_token != token:
                return
            item = ActionExecution.model_validate(row.payload)
            item.last_checked_at = now
            item.recovery_exhausted = (item.recovery_attempts >= max_attempts
                                       or (now - item.requested_at).total_seconds() >= max_age_s)
            delay = min(60, 2 ** min(item.recovery_attempts, 6))
            item.next_check_at = None if item.recovery_exhausted else now + timedelta(seconds=delay)
            row.payload = item.model_dump(mode="json")
            row.recovery_token = row.recovery_until = None
