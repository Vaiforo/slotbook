"""Durable daily AI call budget.

Revision ID: b8f218ca7d10
Revises: 9ad14f00be01
"""

import sqlalchemy as sa
from alembic import op

revision = "b8f218ca7d10"
down_revision = "9ad14f00be01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_usage",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("calls", sa.Integer(), nullable=False),
        sa.CheckConstraint("calls > 0", name="ai_usage_positive_calls"),
        sa.PrimaryKeyConstraint("day"),
    )


def downgrade() -> None:
    op.drop_table("ai_usage")
