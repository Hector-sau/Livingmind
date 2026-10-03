"""Durable *virtual* hardware. State and receipt commit atomically in SQLite.

This property is possible because the device is simulated inside the transaction.
A physical vendor write cannot share this transaction and still requires reconciliation.
"""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from app.adapters.protocol import DeviceCommandReceipt, DeviceCommandRequest
from app.adapters.virtual.devices import CAPABILITIES
from app.contracts import DeviceState


class PersistentVirtualGateway:
    def __init__(self, path: str, spaces: dict[str, dict]):
        self.path, self.initial = path, spaces
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS spaces (id TEXT PRIMARY KEY, epoch INTEGER NOT NULL, state TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS receipts (id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, payload TEXT NOT NULL)")
            for space_id in spaces:
                db.execute("INSERT OR IGNORE INTO spaces VALUES (?,0,?)", (space_id, self.seed_state(space_id).model_dump_json()))

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def seed_state(self, space_id, version=0):
        return DeviceState(space_id=space_id, **self.initial[space_id], version=version,
                           updated_at=datetime.now(timezone.utc), source="virtual_device")

    @staticmethod
    def decode(raw):
        body = json.loads(raw)
        if body["observed_at"]:
            body["observed_at"] = datetime.fromisoformat(body["observed_at"])
        return DeviceCommandReceipt(**body)

    def state(self, space_id):
        with self.transaction() as db:
            row = db.execute("SELECT state FROM spaces WHERE id=?", (space_id,)).fetchone()
            if row is None:
                raise KeyError(space_id)
            return DeviceState.model_validate_json(row[0])

    def fence(self, space_id, epoch):
        with self.transaction() as db:
            if not db.execute("UPDATE spaces SET epoch=MAX(epoch,?) WHERE id=?", (epoch, space_id)).rowcount:
                raise KeyError(space_id)

    def reset(self, space_id, epoch):
        # A reset is fenced too; a delayed reset cannot undo a newer stop or reset.
        with self.transaction() as db:
            row = db.execute("SELECT epoch,state FROM spaces WHERE id=?", (space_id,)).fetchone()
            if row is None:
                raise KeyError(space_id)
            if epoch <= row[0]:
                return False
            state = self.seed_state(space_id, DeviceState.model_validate_json(row[1]).version + 1)
            db.execute("UPDATE spaces SET epoch=?,state=? WHERE id=?", (epoch, state.model_dump_json(), space_id))
            return True  # receipts are deliberately retained across demo resets

    def query(self, action_id):
        with self.transaction() as db:
            row = db.execute("SELECT payload FROM receipts WHERE id=?", (action_id,)).fetchone()
            return self.decode(row[0]) if row else None

    def submit(self, req: DeviceCommandRequest):
        fields = asdict(req)
        fields.pop("requested_at")  # retry transport timestamps do not change command identity
        fingerprint = json.dumps(fields, sort_keys=True)
        space_id, separator, device = req.device_id.rpartition(":")
        with self.transaction() as db:
            prior = db.execute("SELECT fingerprint,payload FROM receipts WHERE id=?", (req.action_id,)).fetchone()
            if prior:
                if prior[0] == fingerprint:
                    return self.decode(prior[1])
                return DeviceCommandReceipt(req.action_id, "rejected", None, None, "rejected", "actionId 与原命令不一致")
            row = db.execute("SELECT epoch,state FROM spaces WHERE id=?", (space_id,)).fetchone()
            cap = next((c for c in CAPABILITIES if c.device == req.device_type and c.command == req.command), None)
            valid = (separator and row is not None and device == req.device_type and cap is not None
                     and cap.min <= req.value <= cap.max and (not cap.integer or float(req.value).is_integer()))
            if not valid or req.service_epoch < row[0]:
                receipt = DeviceCommandReceipt(req.action_id, "rejected", None, None, "rejected", "设备、范围或空间代次无效")
            else:
                state = DeviceState.model_validate_json(row[1])
                field = {"light": "light_brightness", "ac": "ac_target_temp_c", "curtain": "curtain_open_percent"}[req.device_type]
                now = datetime.now(timezone.utc)
                value = int(req.value) if cap.integer else float(req.value)
                state = state.model_copy(update={field: value, "version": state.version + 1, "updated_at": now})
                db.execute("UPDATE spaces SET epoch=?,state=? WHERE id=?", (max(row[0], req.service_epoch), state.model_dump_json(), space_id))
                receipt = DeviceCommandReceipt(req.action_id, "completed", value, now)
            db.execute("INSERT INTO receipts VALUES (?,?,?)", (req.action_id, fingerprint, json.dumps(asdict(receipt), default=str)))
            return receipt
