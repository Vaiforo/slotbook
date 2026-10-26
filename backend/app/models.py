from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    normalized_email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint(
            "normalized_email = lower(trim(normalized_email)) AND normalized_email <> ''",
            name="normalized_email_format",
        ),
    )


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    __table_args__ = (
        CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="session_token_hash_format"),
        CheckConstraint("csrf_token_hash ~ '^[0-9a-f]{64}$'", name="csrf_token_hash_format"),
    )


class Specialist(Base):
    __tablename__ = "specialists"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), unique=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    timezone: Mapped[str] = mapped_column(String(100), server_default="Asia/Omsk")
    __table_args__ = (
        CheckConstraint(
            "slug <> '' AND display_name <> '' AND timezone <> ''", name="specialist_nonempty"
        ),
    )


class Slot(Base):
    __tablename__ = "slots"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    specialist_id: Mapped[UUID] = mapped_column(ForeignKey("specialists.id", ondelete="RESTRICT"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(10), server_default="open")
    __table_args__ = (
        CheckConstraint("state IN ('open', 'closed')", name="slot_state"),
        CheckConstraint("ends_at = starts_at + interval '30 minutes'", name="slot_duration"),
        ExcludeConstraint(
            ("specialist_id", "="),
            (func.tstzrange(starts_at, ends_at, "[)"), "&&"),
            name="no_overlapping_slots",
            using="gist",
        ),
        Index(
            "open_slots_by_specialist_start",
            "specialist_id",
            "starts_at",
            postgresql_where=text("state = 'open'"),
        ),
    )


class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slot_id: Mapped[UUID] = mapped_column(ForeignKey("slots.id", ondelete="RESTRICT"))
    client_name: Mapped[str] = mapped_column(String(200))
    client_email: Mapped[str] = mapped_column(String(320))
    status: Mapped[str] = mapped_column(String(10), server_default="confirmed")
    manage_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("status IN ('confirmed', 'cancelled')", name="booking_status"),
        CheckConstraint(
            "(status = 'confirmed' AND cancelled_at IS NULL) OR "
            "(status = 'cancelled' AND cancelled_at IS NOT NULL)",
            name="booking_cancellation_state",
        ),
        CheckConstraint(
            "client_name <> '' AND client_email <> ''", name="booking_contact_nonempty"
        ),
        CheckConstraint("manage_token_hash ~ '^[0-9a-f]{64}$'", name="manage_token_hash_format"),
        Index(
            "one_confirmed_booking_per_slot",
            "slot_id",
            unique=True,
            postgresql_where=text("status = 'confirmed'"),
        ),
        Index("bookings_slot_created", "slot_id", "created_at"),
    )
