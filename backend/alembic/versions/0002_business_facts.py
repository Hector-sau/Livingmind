"""plans, services, overnight steps, flags, activity and space epochs

Revision ID: 0002
Revises: 0001
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ids keep the demo's readable form (svc-00007) and never repeat after a restart.
    op.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS livingmind_id_seq START 1"))

    op.create_table(
        "space_state",
        sa.Column("space_id", sa.String(64), primary_key=True),
        sa.Column("epoch", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "plans",
        sa.Column("plan_id", sa.String(64), primary_key=True),
        sa.Column("space_id", sa.String(64), nullable=False, index=True),
        sa.Column("person_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("epoch", sa.Integer(), nullable=False),
        sa.Column("service_id", sa.String(64), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("results", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "services",
        sa.Column("service_id", sa.String(64), primary_key=True),
        sa.Column("space_id", sa.String(64), nullable=False, index=True),
        sa.Column("active_space_id", sa.String(64), nullable=True),
        sa.Column("person_id", sa.String(64), nullable=False),
        sa.Column("plan_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # At most one active service per space, enforced by the database, not only by the lock.
    op.create_index("uq_services_active_space", "services", ["active_space_id"], unique=True)
    op.create_table(
        "scheduled_steps",
        sa.Column("step_id", sa.String(64), primary_key=True),
        sa.Column("service_id", sa.String(64), nullable=False, index=True),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
    )
    op.create_table(
        "service_flags",
        sa.Column("service_id", sa.String(64), primary_key=True),
        sa.Column("flag", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "activity_records",
        sa.Column("seq", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("activity_id", sa.String(64), nullable=False, unique=True),
        sa.Column("space_id", sa.String(64), nullable=False, index=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("activity_records")
    op.drop_table("service_flags")
    op.drop_table("scheduled_steps")
    op.drop_index("uq_services_active_space", table_name="services")
    op.drop_table("services")
    op.drop_table("plans")
    op.drop_table("space_state")
    op.execute(sa.text("DROP SEQUENCE IF EXISTS livingmind_id_seq"))
