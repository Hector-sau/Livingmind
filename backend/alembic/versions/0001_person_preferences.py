"""person_preferences: each person's own rest preference

Revision ID: 0001
Revises:
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "person_preferences",
        sa.Column("person_id", sa.String(64), primary_key=True),
        sa.Column("light_brightness", sa.Integer(), nullable=False),
        sa.Column("ac_target_temp_c", sa.Float(), nullable=False),
        sa.Column("curtain_open_percent", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("light_brightness between 0 and 100", name="ck_person_pref_light"),
        sa.CheckConstraint("ac_target_temp_c between 16 and 30", name="ck_person_pref_ac"),
        sa.CheckConstraint("curtain_open_percent between 0 and 100", name="ck_person_pref_curtain"),
    )


def downgrade() -> None:
    op.drop_table("person_preferences")
