"""PostgreSQL persistence. Optional: without LIVINGMIND_DATABASE_URL the demo keeps
running fully in memory, exactly as before (see app/config.py::DATABASE_URL)."""

from app.db.session import database_configured, engine, session_scope

__all__ = ["database_configured", "engine", "session_scope"]
