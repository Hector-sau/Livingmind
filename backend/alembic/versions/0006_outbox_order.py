"""Give committed outbox rows a deterministic local ordering key.

Revision ID: 0006
Revises: 0005

Pre-existing rows receive sequence numbers during migration; their historical order
cannot be reconstructed more precisely than the old timestamp + UUID order.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("CREATE SEQUENCE livingmind_outbox_seq"))
    op.add_column("outbox_events", sa.Column("seq", sa.BigInteger(), nullable=True))
    op.execute(sa.text("""
        UPDATE outbox_events AS target
        SET seq = numbered.seq
        FROM (
            SELECT event_id, row_number() OVER (ORDER BY created_at, event_id) AS seq
            FROM outbox_events
        ) AS numbered
        WHERE target.event_id = numbered.event_id
    """))
    op.execute(sa.text("SELECT setval('livingmind_outbox_seq', COALESCE((SELECT MAX(seq) FROM outbox_events), 0) + 1, false)"))
    op.alter_column("outbox_events", "seq", nullable=False, server_default=sa.text("nextval('livingmind_outbox_seq')"))
    op.create_index("uq_outbox_seq", "outbox_events", ["seq"], unique=True)
    op.create_index("ix_outbox_space_seq", "outbox_events", ["space_id", "seq"])


def downgrade() -> None:
    op.drop_index("ix_outbox_space_seq", table_name="outbox_events")
    op.drop_index("uq_outbox_seq", table_name="outbox_events")
    op.drop_column("outbox_events", "seq")
    op.execute(sa.text("DROP SEQUENCE livingmind_outbox_seq"))
