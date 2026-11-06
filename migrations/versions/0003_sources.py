"""Configured official research feeds."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
    )


def downgrade():
    op.drop_table("sources")
