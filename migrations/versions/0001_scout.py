"""Initial scout foundation schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "source_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("content_id", sa.String(100), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("author", sa.String(200)),
        sa.Column("published_at", sa.String(100)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("transcript", sa.Text()),
        sa.Column("transcript_provenance", sa.Text()),
        sa.Column("research", sa.Text()),
        sa.Column("score", sa.Float()),
        sa.UniqueConstraint("platform", "content_id"),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("source_items.id"), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("previous", sa.String(30), nullable=False),
        sa.Column("current", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "daily_reports",
        sa.Column("day", sa.String(10), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
    )


def downgrade():
    op.drop_table("daily_reports")
    op.drop_table("audit_logs")
    op.drop_table("source_items")
