"""persist resumable clarification state

Revision ID: 0004
Revises: 0003
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pending_clarifications",
        sa.Column("conversation_id", sa.String(120), primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("person_id", sa.String(64), nullable=False),
        sa.Column("space_id", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_pending_clarifications_space_id", "pending_clarifications", ["space_id"])


def downgrade() -> None:
    op.drop_index("ix_pending_clarifications_space_id", table_name="pending_clarifications")
    op.drop_table("pending_clarifications")
