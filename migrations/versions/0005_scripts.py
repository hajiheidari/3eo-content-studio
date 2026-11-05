"""Immutable script revisions and source snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("conversations", sa.Column("pending_script_id", sa.Integer()))
    op.create_table(
        "scripts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("source_items.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("snapshot", sa.Text(), nullable=False),
        sa.Column("content", sa.Text()),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("revision_notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("item_id", "revision"),
    )


def downgrade():
    op.drop_table("scripts")
    op.drop_column("conversations", "pending_script_id")
