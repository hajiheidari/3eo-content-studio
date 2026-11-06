"""Private preview renders with exact final approval."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rendering_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("script_id", sa.Integer(), sa.ForeignKey("scripts.id"), nullable=False),
        sa.Column("script_hash", sa.String(64), nullable=False),
        sa.Column("voice_asset_id", sa.Integer(), sa.ForeignKey("media_assets.id"), nullable=False),
        sa.Column(
            "screen_asset_id", sa.Integer(), sa.ForeignKey("media_assets.id"), nullable=False
        ),
        sa.Column("storage_key", sa.String(32), nullable=False, unique=True),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("sha256", sa.String(64)),
        sa.Column("metadata_json", sa.Text()),
        sa.Column("started_at", sa.Float(), nullable=False),
        sa.UniqueConstraint("script_id", "voice_asset_id", "screen_asset_id"),
    )


def downgrade():
    op.drop_table("rendering_jobs")
