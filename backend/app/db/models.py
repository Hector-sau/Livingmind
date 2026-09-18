"""ORM models. One table per business fact; schema changes go through Alembic."""

from __future__ import annotations

from datetime import datetime

from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Float, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
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


class SpaceStateRow(Base):
    """Per-space epoch. A stop or a demo reset increments it, which invalidates older plans."""

    __tablename__ = "space_state"

    space_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PlanRow(Base):
    """A plan plus its execution record. Columns carry what we query on; payload is the contract."""

    __tablename__ = "plans"

    plan_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    space_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    person_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    service_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    results: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[Any] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ServiceRow(Base):
    """One rest service. ``active_space_id`` is null unless the service is active, so the
    partial unique index below enforces "at most one active service per space" in the database."""

    __tablename__ = "services"
    __table_args__ = (
        Index("uq_services_active_space", "active_space_id", unique=True),
    )

    service_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    space_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    active_space_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    person_id: Mapped[str] = mapped_column(String(64), nullable=False)
    plan_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[Any] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ScheduledStepRow(Base):
    """One overnight step. Claimed with an UPDATE ... WHERE status='pending' so it runs once."""

    __tablename__ = "scheduled_steps"

    step_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    service_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ServiceFlagRow(Base):
    """Work in flight on a service (adjustment planning, clock advance)."""

    __tablename__ = "service_flags"

    service_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    flag: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[Any] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ActivityRow(Base):
    """Append-only activity log. Written synchronously; the evidence panel reads it directly."""

    __tablename__ = "activity_records"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activity_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    space_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
