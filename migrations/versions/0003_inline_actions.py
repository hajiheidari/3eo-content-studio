"""Persist report/action keyboards alongside queued Telegram messages."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("telegram_outbox", sa.Column("reply_markup", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("telegram_outbox", "reply_markup")
