"""Source backlog and generated visual reservations."""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "discovery_sweeps",
        sa.Column("day", sa.String(10), primary_key=True),
        sa.Column("state", sa.String(20), nullable=False),
    )
    op.create_table(
        "visual_jobs",
        sa.Column("script_id", sa.Integer(), sa.ForeignKey("scripts.id"), primary_key=True),
        sa.Column("script_hash", sa.String(64), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("started_at", sa.Float(), nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("media_assets.id")),
    )
    op.create_table(
        "production_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "item_id", sa.Integer(), sa.ForeignKey("source_items.id"), unique=True, nullable=False
        ),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("started_at", sa.Float(), nullable=False),
        sa.Column("script_id", sa.Integer(), sa.ForeignKey("scripts.id")),
        sa.Column("delivery_state", sa.String(30), nullable=False),
    )


def downgrade():
    op.drop_table("discovery_sweeps")
    op.drop_table("production_tasks")
    op.drop_table("visual_jobs")
