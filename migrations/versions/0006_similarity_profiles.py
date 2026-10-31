"""Nullable lexical profiles; old records are explicitly backfilled in bounded batches."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("source_items", sa.Column("similarity_profile", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("source_items", "similarity_profile")
