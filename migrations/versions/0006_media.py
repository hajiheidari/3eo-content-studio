"""Private version-bound media and upload context."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("conversations", sa.Column("upload_script_id", sa.Integer()))
    op.add_column("conversations", sa.Column("upload_kind", sa.String(20)))
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("script_id", sa.Integer(), sa.ForeignKey("scripts.id"), nullable=False),
        sa.Column("script_hash", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("storage_key", sa.String(32), nullable=False, unique=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("byte_count", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("processing_json", sa.Text()),
        sa.Column("processing_started", sa.Float()),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("script_id", "kind", "sha256"),
    )


def downgrade():
    op.drop_table("media_assets")
    op.drop_column("conversations", "upload_kind")
    op.drop_column("conversations", "upload_script_id")
