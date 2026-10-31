"""Durable Telegram delivery, polling offsets and mutation replay protection."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("source_items", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.create_table(
        "mutation_receipts",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
    )
    op.create_table(
        "worker_cursors",
        sa.Column("name", sa.String(100), primary_key=True),
        sa.Column("offset", sa.BigInteger(), nullable=False),
        sa.Column("owner", sa.String(40)),
        sa.Column("expires_at", sa.Float(), nullable=False),
    )
    op.create_table(
        "telegram_outbox",
        sa.Column("key", sa.String(160), primary_key=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.Float(), nullable=False),
        sa.Column("message_id", sa.BigInteger()),
        sa.Column("error", sa.String(100)),
    )


def downgrade():
    op.drop_table("telegram_outbox")
    op.drop_table("worker_cursors")
    op.drop_table("mutation_receipts")
    op.drop_column("source_items", "version")
