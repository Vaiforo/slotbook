"""Account roles and professional profile foundation."""

import sqlalchemy as sa
from alembic import op

revision = "c1420a01"
down_revision = "b8f218ca7d10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, kind, default in [
        ("role", sa.String(20), "client"),
        ("full_name", sa.String(200), ""),
        ("phone", sa.String(30), ""),
        ("timezone", sa.String(100), "Asia/Omsk"),
    ]:
        op.add_column("users", sa.Column(name, kind, nullable=False, server_default=default))
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "users",
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.execute(
        "UPDATE users SET role = 'specialist', full_name = s.display_name, "
        "timezone = s.timezone FROM specialists s WHERE s.user_id = users.id"
    )
    op.create_check_constraint("user_role", "users", "role IN ('client', 'specialist')")
    categories = op.create_table(
        "specialist_categories",
        sa.Column("code", sa.String(30), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
    )
    op.bulk_insert(
        categories,
        [
            {"code": "medicine", "name": "Медицина", "sort_order": 1},
            {"code": "plumbing", "name": "Сантехника", "sort_order": 2},
            {"code": "law", "name": "Юриспруденция", "sort_order": 3},
            {"code": "delivery", "name": "Доставка", "sort_order": 4},
        ],
    )
    op.add_column(
        "specialists",
        sa.Column("category_code", sa.String(30), sa.ForeignKey("specialist_categories.code")),
    )
    for name, length, default in [
        ("specialization", 200, ""),
        ("short_description", 500, ""),
        ("description", 10000, ""),
        ("city", 100, ""),
        ("work_formats", 100, ""),
        ("workplace", 500, ""),
        ("service_area", 500, ""),
        ("publication_status", 20, "draft"),
    ]:
        op.add_column(
            "specialists",
            sa.Column(name, sa.String(length), nullable=False, server_default=default),
        )
    op.add_column("specialists", sa.Column("experience_years", sa.Integer()))
    op.add_column(
        "specialists",
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_check_constraint(
        "specialist_publication_status",
        "specialists",
        "publication_status IN ('draft', 'published')",
    )
    op.create_check_constraint(
        "specialist_experience",
        "specialists",
        "experience_years IS NULL OR experience_years BETWEEN 0 AND 80",
    )


def downgrade() -> None:
    op.drop_constraint("specialist_experience", "specialists")
    op.drop_constraint("specialist_publication_status", "specialists")
    for name in [
        "category_code",
        "specialization",
        "short_description",
        "description",
        "experience_years",
        "city",
        "work_formats",
        "workplace",
        "service_area",
        "publication_status",
        "updated_at",
    ]:
        op.drop_column("specialists", name)
    op.drop_table("specialist_categories")
    op.drop_constraint("user_role", "users")
    for name in ["role", "full_name", "phone", "timezone", "is_active", "updated_at"]:
        op.drop_column("users", name)
