"""Persist synthetic catalog extension horizon and next Wednesday."""

import sqlalchemy as sa
from alembic import op

revision = "f1420a04"
down_revision = "e1420a03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_schedules",
        sa.Column("name", sa.String(50), primary_key=True),
        sa.Column("initial_starts_on", sa.Date(), nullable=False),
        sa.Column("generated_through", sa.Date(), nullable=False),
        sa.Column("next_extension_on", sa.Date(), nullable=False),
        sa.CheckConstraint("generated_through >= initial_starts_on", name="catalog_schedule_range"),
        sa.CheckConstraint(
            "extract(isodow from next_extension_on) = 3", name="catalog_schedule_wednesday"
        ),
    )


def downgrade() -> None:
    op.drop_table("catalog_schedules")
