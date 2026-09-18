"""Where a person's own preference is stored.

Two implementations behind one protocol:
- InMemoryPreferenceRepository: the demo default, resets with the process.
- SqlPreferenceRepository: PostgreSQL, survives restarts (T2).

The service layer never touches the ORM directly, so tests can run against either one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol

from sqlalchemy import select

from app.contracts import RestPreference
from app.db.models import PersonPreferenceRow
from app.db.session import session_scope


@dataclass(frozen=True)
class StoredPreference:
    preference: RestPreference
    updated_at: Optional[datetime]  # None = still the seeded value, never edited


class PreferenceRepository(Protocol):
    def get(self, person_id: str) -> Optional[StoredPreference]: ...

    def put(self, person_id: str, preference: RestPreference, updated_at: Optional[datetime]) -> None: ...

    def clear(self) -> None:
        """Remove every stored preference (demo reset re-seeds afterwards)."""
        ...


class InMemoryPreferenceRepository:
    def __init__(self) -> None:
        self._rows: dict[str, StoredPreference] = {}

    def get(self, person_id: str) -> Optional[StoredPreference]:
        return self._rows.get(person_id)

    def put(self, person_id: str, preference: RestPreference, updated_at: Optional[datetime]) -> None:
        self._rows[person_id] = StoredPreference(preference=preference.model_copy(), updated_at=updated_at)

    def clear(self) -> None:
        self._rows.clear()


class SqlPreferenceRepository:
    """PostgreSQL-backed. Each call is its own short transaction."""

    def get(self, person_id: str) -> Optional[StoredPreference]:
        with session_scope() as session:
            row = session.scalar(select(PersonPreferenceRow).where(PersonPreferenceRow.person_id == person_id))
            if row is None:
                return None
            return StoredPreference(
                preference=RestPreference(
                    light_brightness=row.light_brightness,
                    ac_target_temp_c=row.ac_target_temp_c,
                    curtain_open_percent=row.curtain_open_percent,
                ),
                updated_at=row.updated_at,
            )

    def put(self, person_id: str, preference: RestPreference, updated_at: Optional[datetime]) -> None:
        with session_scope() as session:
            row = session.get(PersonPreferenceRow, person_id)
            if row is None:
                row = PersonPreferenceRow(person_id=person_id)
                session.add(row)
            row.light_brightness = preference.light_brightness
            row.ac_target_temp_c = preference.ac_target_temp_c
            row.curtain_open_percent = preference.curtain_open_percent
            row.updated_at = updated_at

    def clear(self) -> None:
        with session_scope() as session:
            for row in session.scalars(select(PersonPreferenceRow)).all():
                session.delete(row)
