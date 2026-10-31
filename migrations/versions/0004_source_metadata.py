"""Cached source metadata and conservative daily API reservations."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("source_items", sa.Column("source_metadata", sa.Text(), nullable=True))
    op.create_table("api_usage", sa.Column("key", sa.String(100), primary_key=True),
                    sa.Column("count", sa.Integer(), nullable=False))


def downgrade():
    op.drop_table("api_usage")
    op.drop_column("source_items", "source_metadata")
