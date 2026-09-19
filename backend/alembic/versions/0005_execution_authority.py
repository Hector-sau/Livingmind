"""execution authority and durable command ledger

Revision ID: 0005
Revises: 0004
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "policy_decisions",
        sa.Column("decision_id", sa.String(64), primary_key=True),
        sa.Column("plan_id", sa.String(64), nullable=False),
        sa.Column("space_id", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_policy_decisions_plan_id", "policy_decisions", ["plan_id"])
    op.create_index("ix_policy_decisions_space_id", "policy_decisions", ["space_id"])

    op.create_table(
        "execution_grants",
        sa.Column("grant_id", sa.String(64), primary_key=True),
        sa.Column("plan_id", sa.String(64), nullable=False),
        sa.Column("service_id", sa.String(64), nullable=True),
        sa.Column("space_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("service_epoch", sa.Integer(), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_execution_grants_plan_id", "execution_grants", ["plan_id"])
    op.create_index("ix_execution_grants_service_id", "execution_grants", ["service_id"])
    op.create_index("ix_execution_grants_space_id", "execution_grants", ["space_id"])

    op.create_table(
        "action_executions",
        sa.Column("action_id", sa.String(64), primary_key=True),
        sa.Column("grant_id", sa.String(64), nullable=False),
        sa.Column("plan_id", sa.String(64), nullable=False),
        sa.Column("service_id", sa.String(64), nullable=True),
        sa.Column("space_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("service_epoch", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_action_executions_grant_id", "action_executions", ["grant_id"])
    op.create_index("ix_action_executions_plan_id", "action_executions", ["plan_id"])
    op.create_index("ix_action_executions_service_id", "action_executions", ["service_id"])
    op.create_index("ix_action_executions_space_id", "action_executions", ["space_id"])
    op.create_index("ix_action_executions_status", "action_executions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_action_executions_status", table_name="action_executions")
    op.drop_index("ix_action_executions_space_id", table_name="action_executions")
    op.drop_index("ix_action_executions_service_id", table_name="action_executions")
    op.drop_index("ix_action_executions_plan_id", table_name="action_executions")
    op.drop_index("ix_action_executions_grant_id", table_name="action_executions")
    op.drop_table("action_executions")
    op.drop_index("ix_execution_grants_space_id", table_name="execution_grants")
    op.drop_index("ix_execution_grants_service_id", table_name="execution_grants")
    op.drop_index("ix_execution_grants_plan_id", table_name="execution_grants")
    op.drop_table("execution_grants")
    op.drop_index("ix_policy_decisions_space_id", table_name="policy_decisions")
    op.drop_index("ix_policy_decisions_plan_id", table_name="policy_decisions")
    op.drop_table("policy_decisions")
