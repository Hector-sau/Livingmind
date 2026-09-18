"""Engine and session handling.

Synchronous stack on purpose: the API routes, the service lock and the executor are all
synchronous (see docs/technology-architecture.md). Async would have to be a separate project.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import config

_engine: Optional[Engine] = None
_factory: Optional[sessionmaker[Session]] = None


def database_configured() -> bool:
    return bool(config.DATABASE_URL)


def engine() -> Engine:
    """One pooled engine per process, created on first use."""
    global _engine, _factory
    if _engine is None:
        if not config.DATABASE_URL:
            raise RuntimeError("LIVINGMIND_DATABASE_URL is not set; the demo runs in memory")
        _engine = create_engine(config.DATABASE_URL, pool_pre_ping=True, future=True)
        _factory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def session_factory() -> sessionmaker[Session]:
    engine()
    assert _factory is not None
    return _factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """One transaction. Commits on success, rolls back on any exception."""
    session = session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine() -> None:
    """Tests only: drop the cached engine so a new DATABASE_URL takes effect."""
    global _engine, _factory
    if _engine is not None:
        _engine.dispose()
    _engine, _factory = None, None
