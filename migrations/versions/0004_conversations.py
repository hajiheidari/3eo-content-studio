"""Evidence classification and durable private conversation context."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("source_items", sa.Column("evidence_kind", sa.String(30)))
    op.execute(
        "UPDATE source_items SET evidence_kind = CASE WHEN transcript_provenance LIKE 'Public feed excerpt%' THEN 'feed_excerpt' ELSE 'transcript' END WHERE transcript IS NOT NULL"
    )
    op.create_table(
        "conversations",
        sa.Column("actor", sa.String(100), primary_key=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("source_items.id"), nullable=False),
        sa.Column("evidence_kind", sa.String(30), nullable=False),
    )


def downgrade():
    op.drop_table("conversations")
    op.drop_column("source_items", "evidence_kind")
