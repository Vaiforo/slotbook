"""initial_schema"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "768bb00f10e5"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("normalized_email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "normalized_email = lower(trim(normalized_email)) AND normalized_email <> ''",
            name="normalized_email_format",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_email"),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("csrf_token_hash ~ '^[0-9a-f]{64}$'", name="csrf_token_hash_format"),
        sa.CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="session_token_hash_format"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(op.f("ix_sessions_expires_at"), "sessions", ["expires_at"], unique=False)
    op.create_table(
        "specialists",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("timezone", sa.String(length=100), server_default="Asia/Omsk", nullable=False),
        sa.CheckConstraint(
            "slug <> '' AND display_name <> '' AND timezone <> ''", name="specialist_nonempty"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "slots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("specialist_id", sa.Uuid(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=10), server_default="open", nullable=False),
        postgresql.ExcludeConstraint(
            (sa.column("specialist_id"), "="),
            (sa.text("tstzrange(starts_at, ends_at, '[)')"), "&&"),
            using="gist",
            name="no_overlapping_slots",
        ),
        sa.CheckConstraint("ends_at = starts_at + interval '30 minutes'", name="slot_duration"),
        sa.CheckConstraint("state IN ('open', 'closed')", name="slot_state"),
        sa.ForeignKeyConstraint(["specialist_id"], ["specialists.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "open_slots_by_specialist_start",
        "slots",
        ["specialist_id", "starts_at"],
        unique=False,
        postgresql_where=sa.text("state = 'open'"),
    )
    op.create_table(
        "bookings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slot_id", sa.Uuid(), nullable=False),
        sa.Column("client_name", sa.String(length=200), nullable=False),
        sa.Column("client_email", sa.String(length=320), nullable=False),
        sa.Column("status", sa.String(length=10), server_default="confirmed", nullable=False),
        sa.Column("manage_token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(status = 'confirmed' AND cancelled_at IS NULL) OR "
            "(status = 'cancelled' AND cancelled_at IS NOT NULL)",
            name="booking_cancellation_state",
        ),
        sa.CheckConstraint(
            "client_name <> '' AND client_email <> ''", name="booking_contact_nonempty"
        ),
        sa.CheckConstraint("manage_token_hash ~ '^[0-9a-f]{64}$'", name="manage_token_hash_format"),
        sa.CheckConstraint("status IN ('confirmed', 'cancelled')", name="booking_status"),
        sa.ForeignKeyConstraint(["slot_id"], ["slots.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("manage_token_hash"),
    )
    op.create_index("bookings_slot_created", "bookings", ["slot_id", "created_at"], unique=False)
    op.create_index(
        "one_confirmed_booking_per_slot",
        "bookings",
        ["slot_id"],
        unique=True,
        postgresql_where=sa.text("status = 'confirmed'"),
    )


def downgrade() -> None:
    op.drop_index(
        "one_confirmed_booking_per_slot",
        table_name="bookings",
        postgresql_where=sa.text("status = 'confirmed'"),
    )
    op.drop_index("bookings_slot_created", table_name="bookings")
    op.drop_table("bookings")
    op.drop_index(
        "open_slots_by_specialist_start",
        table_name="slots",
        postgresql_where=sa.text("state = 'open'"),
    )
    op.drop_table("slots")
    op.drop_table("specialists")
    op.drop_index(op.f("ix_sessions_expires_at"), table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
