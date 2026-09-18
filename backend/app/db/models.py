"""ORM models. One table per business fact; schema changes go through Alembic."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PersonPreferenceRow(Base):
    """One person's own rest preference. Never read by anyone else (enforced in the service)."""

    __tablename__ = "person_preferences"
    __table_args__ = (
        CheckConstraint("light_brightness between 0 and 100", name="ck_person_pref_light"),
        CheckConstraint("ac_target_temp_c between 16 and 30", name="ck_person_pref_ac"),
        CheckConstraint("curtain_open_percent between 0 and 100", name="ck_person_pref_curtain"),
    )

    person_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    light_brightness: Mapped[int] = mapped_column(Integer, nullable=False)
    ac_target_temp_c: Mapped[float] = mapped_column(Float, nullable=False)
    curtain_open_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    # Null until the person edits it: a seeded value is not an edit.
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
