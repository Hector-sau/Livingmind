"""Record who owns in-flight work; persist shared energy and undo state.

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007"
down_revision = "0006"
branch_labels = depends_on = None


def upgrade():
    for table in ("action_executions", "scheduled_steps", "service_flags"):
        op.add_column(table, sa.Column("owner_id", sa.String(64), nullable=True))
    op.create_table("shared_settings", sa.Column("key", sa.String(128), primary_key=True), sa.Column("payload", JSONB, nullable=False))


def downgrade():
    op.drop_table("shared_settings")
    for table in ("service_flags", "scheduled_steps", "action_executions"):
        op.drop_column(table, "owner_id")
