"""Transactional notification outbox and delivery state."""

import sqlalchemy as sa
from alembic import op

revision = "9ad14f00be01"
down_revision = "768bb00f10e5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "booking_id",
            sa.Uuid(),
            sa.ForeignKey("bookings.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column(
            "next_publish_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('booking_created', 'booking_cancelled')", name="outbox_kind"),
    )
    op.create_index("ix_outbox_events_next_publish_at", "outbox_events", ["next_publish_at"])
    op.create_table(
        "notification_deliveries",
        sa.Column(
            "event_id",
            sa.Uuid(),
            sa.ForeignKey("outbox_events.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("channel", sa.String(10), primary_key=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(50)),
        sa.CheckConstraint("channel = 'email'", name="notification_channel"),
        sa.CheckConstraint(
            "status IN ('pending', 'retrying', 'sent', 'failed')", name="notification_status"
        ),
        sa.CheckConstraint("attempts >= 0", name="notification_attempts"),
    )


def downgrade():
    op.drop_table("notification_deliveries")
    op.drop_index("ix_outbox_events_next_publish_at", table_name="outbox_events")
    op.drop_table("outbox_events")
