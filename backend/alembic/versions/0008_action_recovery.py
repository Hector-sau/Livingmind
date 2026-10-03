"""Track manual actions without fake plans; lease read-only recovery work.

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = depends_on = None


def upgrade():
    op.alter_column("action_executions", "grant_id", nullable=True)
    op.alter_column("action_executions", "plan_id", nullable=True)
    op.add_column("action_executions", sa.Column("recovery_token", sa.String(64), nullable=True))
    op.add_column("action_executions", sa.Column("recovery_until", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    # Old code cannot represent standalone commands. Refuse silent evidence loss.
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM action_executions WHERE plan_id IS NULL OR grant_id IS NULL)")):
        raise RuntimeError("0008 downgrade requires archiving/removing standalone action evidence first; do not downgrade a live database")
    op.drop_column("action_executions", "recovery_until")
    op.drop_column("action_executions", "recovery_token")
    op.alter_column("action_executions", "plan_id", nullable=False)
    op.alter_column("action_executions", "grant_id", nullable=False)
