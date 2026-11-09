"""Professional services and catalog indexes."""

import sqlalchemy as sa
from alembic import op

revision = "d1420a02"
down_revision = "c1420a01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "specialist_services",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "specialist_id",
            sa.Uuid(),
            sa.ForeignKey("specialists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_specialist_services_specialist_id", "specialist_services", ["specialist_id"]
    )
    op.create_index(
        "published_specialists_category_city",
        "specialists",
        ["category_code", "city"],
        postgresql_where=sa.text("publication_status = 'published'"),
    )


def downgrade() -> None:
    op.drop_index("published_specialists_category_city", "specialists")
    op.drop_table("specialist_services")
