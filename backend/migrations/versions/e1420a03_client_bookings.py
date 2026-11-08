"""Link new bookings to client accounts and remove only the known legacy demo."""

from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision = "e1420a03"
down_revision = "d1420a02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bookings",
        sa.Column("client_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
    )
    op.create_index("ix_bookings_client_user_id", "bookings", ["client_user_id"])
    # Run migrations with dispatchers/workers stopped. Never match by name or email.
    conn = op.get_bind()
    specialist = uuid5(NAMESPACE_URL, "slotbook/demo/specialist")
    user = uuid5(NAMESPACE_URL, "slotbook/demo/user")
    params = {"specialist": specialist, "user": user}
    booking_ids = (
        "SELECT b.id FROM bookings b JOIN slots s ON s.id=b.slot_id "
        "WHERE s.specialist_id=:specialist"
    )
    events = f"SELECT id FROM outbox_events WHERE booking_id IN ({booking_ids})"
    conn.execute(
        sa.text(f"DELETE FROM notification_deliveries WHERE event_id IN ({events})"), params
    )
    conn.execute(sa.text(f"DELETE FROM outbox_events WHERE booking_id IN ({booking_ids})"), params)
    conn.execute(sa.text(f"DELETE FROM bookings WHERE id IN ({booking_ids})"), params)
    conn.execute(sa.text("DELETE FROM slots WHERE specialist_id=:specialist"), params)
    conn.execute(sa.text("DELETE FROM specialist_services WHERE specialist_id=:specialist"), params)
    conn.execute(sa.text("DELETE FROM specialists WHERE id=:specialist AND user_id=:user"), params)
    conn.execute(sa.text("DELETE FROM sessions WHERE user_id=:user"), params)
    conn.execute(
        sa.text(
            "DELETE FROM users WHERE id=:user AND NOT EXISTS "
            "(SELECT 1 FROM specialists WHERE user_id=:user)"
        ),
        params,
    )


def downgrade() -> None:
    # Removed synthetic demo data is intentionally not reconstructed.
    op.drop_index("ix_bookings_client_user_id", "bookings")
    op.drop_column("bookings", "client_user_id")
