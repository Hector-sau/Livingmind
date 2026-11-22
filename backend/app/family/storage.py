"""SQLite checkpoints and a local, cross-process writer lease for one simulated household."""
import hashlib
import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from .service import FamilyError, FamilyEvening


def _encode_checkpoint(checkpoint):
    # Three domain indexes use tuples, including nested activity tuples in the sensor index.
    state = dict(checkpoint["state"])
    for key in ("recent_signals", "exceptions"):
        state[key] = list(state[key].items())
    return json.dumps({**checkpoint, "state": state}, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _nested_tuple(item):
    return tuple(_nested_tuple(child) for child in item) if isinstance(item, list) else item


def _decode_checkpoint(payload):
    data = json.loads(payload)
    if data.get("version") != 1:
        raise ValueError("Unsupported household checkpoint version")
    state = data["state"]
    state["events"] = {key: tuple(value) for key, value in state["events"].items()}
    for key in ("recent_signals", "exceptions"):
        state[key] = {_nested_tuple(k): v for k, v in state[key]}
    return data


class SQLiteFamilyStore:
    def __init__(self, path, devices):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.writer_path = self.path.with_name(self.path.name + ".writer.sqlite3")
        inventory = json.dumps(devices, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        profile_digest = hashlib.sha256(inventory.encode()).hexdigest()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS family_checkpoint (
                id INTEGER PRIMARY KEY CHECK (id = 1), profile TEXT NOT NULL,
                payload TEXT, view TEXT)""")
            db.execute("INSERT OR IGNORE INTO family_checkpoint(id, profile) VALUES(1, ?)", (profile_digest,))
            if db.execute("SELECT profile FROM family_checkpoint WHERE id=1").fetchone()[0] != profile_digest:
                raise ValueError("This database belongs to a different MIoT profile. Use the original profile or a new file.")

    @contextmanager
    def writer(self, *, wait=True):
        # The lease uses a separate SQLite file: intent, device receipts and the public view
        # can each commit to the data file while the writer still owns the household.
        with closing(sqlite3.connect(self.writer_path, timeout=30 if wait else 0)) as lease:
            try:
                lease.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                    raise
                if wait:
                    raise FamilyError(503, "FAMILY_BUSY", "设备操作仍在进行，请稍后重试。") from exc
                yield False
                return
            try:
                yield True
            finally:
                lease.rollback()

    def load(self):
        with closing(sqlite3.connect(self.path)) as db:
            payload, view = db.execute("SELECT payload, view FROM family_checkpoint WHERE id=1").fetchone()
        if payload is None:
            return None
        return {**_decode_checkpoint(payload), "view": json.loads(view)}

    def view(self):
        with closing(sqlite3.connect(self.path)) as db:
            raw = db.execute("SELECT view FROM family_checkpoint WHERE id=1").fetchone()[0]
        return json.loads(raw) if raw is not None else None

    def save(self, checkpoint):
        record = dict(checkpoint)
        view = record.pop("view")
        payload = _encode_checkpoint(record)
        public = json.dumps(view, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE family_checkpoint SET payload=?, view=? WHERE id=1", (payload, public))


class SharedFamilySession:
    """Readers see a committed snapshot while one local process executes a household mutation."""
    def __init__(self, store, gateway_factory):
        self.store = store
        self.gateway_factory = gateway_factory
        self.state()  # Initialize a new database, or finish an abandoned confirmation.

    def _restore(self):
        return FamilyEvening(gateway_factory=self.gateway_factory, store=self.store)

    def state(self):
        view = self.store.view()
        if view is None:
            with self.store.writer():
                return self._restore().state()
        if view.get("execution"):
            # A live writer keeps the lease across transport I/O. If the owner died,
            # SQLite releases it; only the new owner may decide an unfinished outcome.
            with self.store.writer(wait=False) as acquired:
                if acquired:
                    return self._restore().state()
        return view

    def dispatch(self, method, path, data=None):
        try:
            if method == "GET" and path == "/state":
                return self.state()
            with self.store.writer():
                return self._restore().dispatch(method, path, data)
        except sqlite3.Error as exc:
            raise FamilyError(503, "CHECKPOINT_UNAVAILABLE", "暂时无法读取或保存家庭状态。") from exc
