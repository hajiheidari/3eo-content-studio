"""Metadata, optimistic concurrency and durable Telegram state."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("source_items", sa.Column("title", sa.String(1000)))
    op.add_column("source_items", sa.Column("metadata_provenance", sa.String(300)))
    op.add_column(
        "source_items", sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )
    op.create_table(
        "report_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("day", sa.String(10), sa.ForeignKey("daily_reports.day"), nullable=False),
        sa.Column("recipient", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt", sa.Float(), nullable=False),
        sa.Column("message_id", sa.String(40)),
        sa.UniqueConstraint("day", "recipient"),
    )
    op.create_table(
        "bot_updates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("status", sa.String(20), nullable=False),
    )
    op.create_table(
        "bot_cursor",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("offset", sa.Integer(), nullable=False),
    )


def downgrade():
    op.drop_table("bot_cursor")
    op.drop_table("bot_updates")
    op.drop_table("report_deliveries")
    op.drop_column("source_items", "version")
    op.drop_column("source_items", "metadata_provenance")
    op.drop_column("source_items", "title")
