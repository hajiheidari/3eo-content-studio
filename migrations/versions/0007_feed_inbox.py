"""Isolated public-feed inbox and durable conditional-fetch state."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "feed_states",
        sa.Column("source", sa.String(100), primary_key=True),
        sa.Column("etag", sa.String(500), nullable=True),
        sa.Column("modified", sa.String(500), nullable=True),
        sa.Column("checked_at", sa.Float(), nullable=True),
        sa.Column("success_at", sa.Float(), nullable=True),
        sa.Column("next_at", sa.Float(), nullable=False),
        sa.Column("owner", sa.String(40), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("error", sa.String(100), nullable=True),
    )
    op.create_table(
        "feed_entries",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("source", sa.String(100), sa.ForeignKey("feed_states.source"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("published_at", sa.String(100), nullable=True),
        sa.Column("discovered_at", sa.Float(), nullable=False),
    )


def downgrade():
    op.drop_table("feed_entries")
    op.drop_table("feed_states")
