"""PostgreSQL session locks identify live API processes and serialize remote writes.

No wall-clock TTL: a lock survives slow work and is released when its DB connection
ends. A lost/replaced connection fails closed; stop never takes the execution lock.
This is a bounded demo deployment, not a claim of availability under partitions.
"""
import threading
import uuid

from sqlalchemy import text

from app.db.session import engine


class SessionLock:
    def __init__(self, key):
        self.key, self.connection, self.pid = key, None, None
        self.blocked = True
        self._mutex = threading.Lock()

    def __enter__(self):
        self.connection = engine().connect().execution_options(isolation_level="AUTOCOMMIT")
        try:
            acquired = self.connection.scalar(text("SELECT pg_try_advisory_lock(hashtextextended(:key, 0))"), {"key": self.key})
            self.blocked = not acquired
            self.pid = self.connection.scalar(text("SELECT pg_backend_pid()"))
            return self
        except BaseException:
            self.connection.invalidate()
            self.connection.close()
            raise

    def alive(self):
        with self._mutex:
            if self.blocked or self.connection is None or self.connection.invalidated:
                return False
            try:
                return self.connection.scalar(text("SELECT pg_backend_pid()")) == self.pid
            except Exception:
                return False

    def __exit__(self, *args):
        with self._mutex:
            if self.connection is not None:
                try:
                    if not self.blocked and not self.connection.invalidated:
                        self.connection.execute(text("SELECT pg_advisory_unlock(hashtextextended(:key, 0))"), {"key": self.key})
                except Exception:
                    self.connection.invalidate()
                finally:
                    self.connection.close()
                    self.connection = None


class ExecutionOwner(SessionLock):
    def __init__(self):
        self.owner_id = uuid.uuid4().hex
        super().__init__(f"livingmind-owner:{self.owner_id}")


def owner_is_gone(session, owner_id):
    if owner_id is None:
        return True  # old single-instance rows, only on a coordinated migration/start
    return session.scalar(text("SELECT pg_try_advisory_xact_lock(hashtextextended(:key, 0))"),
                          {"key": f"livingmind-owner:{owner_id}"})
