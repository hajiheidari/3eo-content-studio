"""Durable AI request claims, safe result reuse and research provenance."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("source_items", sa.Column("research_provenance", sa.Text(), nullable=True))
    op.create_table(
        "research_attempts",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.Float(), nullable=False),
        sa.Column("available_at", sa.Float(), nullable=False),
        sa.Column("payload", sa.Text()),
        sa.Column("response_id", sa.String(200)),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("error", sa.String(100)),
    )


def downgrade():
    op.drop_table("research_attempts")
    op.drop_column("source_items", "research_provenance")
