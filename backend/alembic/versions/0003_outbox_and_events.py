"""transactional outbox, delivered domain events, consumer receipts and the service projection

Revision ID: 0003
Revises: 0002
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("space_id", sa.String(64), nullable=False, index=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(500), nullable=True),
    )
    # The publisher only ever looks at unpublished rows, oldest first.
    op.create_index("ix_outbox_pending", "outbox_events", ["published_at", "created_at"])
    op.create_table(
        "domain_events",
        sa.Column("seq", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(64), nullable=False, unique=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("space_id", sa.String(64), nullable=False, index=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "consumer_receipts",
        sa.Column("consumer", sa.String(64), primary_key=True),
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "service_projection",
        sa.Column("service_id", sa.String(64), primary_key=True),
        sa.Column("space_id", sa.String(64), nullable=False, index=True),
        sa.Column("person_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("adjustments", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("device_actions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("events_applied", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("service_projection")
    op.drop_table("consumer_receipts")
    op.drop_table("domain_events")
    op.drop_index("ix_outbox_pending", table_name="outbox_events")
    op.drop_table("outbox_events")
