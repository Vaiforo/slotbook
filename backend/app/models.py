from datetime import date, datetime
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
    role: Mapped[str] = mapped_column(String(20), server_default="client")
    full_name: Mapped[str] = mapped_column(String(200), server_default="")
    phone: Mapped[str] = mapped_column(String(30), server_default="")
    timezone: Mapped[str] = mapped_column(String(100), server_default="Asia/Omsk")
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint("role IN ('client', 'specialist')", name="user_role"),
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


class SpecialistCategory(Base):
    __tablename__ = "specialist_categories"
    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column()


class Specialist(Base):
    __tablename__ = "specialists"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), unique=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    timezone: Mapped[str] = mapped_column(String(100), server_default="Asia/Omsk")
    category_code: Mapped[str | None] = mapped_column(ForeignKey("specialist_categories.code"))
    specialization: Mapped[str] = mapped_column(String(200), server_default="")
    short_description: Mapped[str] = mapped_column(String(500), server_default="")
    description: Mapped[str] = mapped_column(String(10000), server_default="")
    experience_years: Mapped[int | None] = mapped_column()
    city: Mapped[str] = mapped_column(String(100), server_default="")
    work_formats: Mapped[str] = mapped_column(String(100), server_default="")
    workplace: Mapped[str] = mapped_column(String(500), server_default="")
    service_area: Mapped[str] = mapped_column(String(500), server_default="")
    publication_status: Mapped[str] = mapped_column(String(20), server_default="draft")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        CheckConstraint(
            "publication_status IN ('draft', 'published')", name="specialist_publication_status"
        ),
        CheckConstraint(
            "experience_years IS NULL OR experience_years BETWEEN 0 AND 80",
            name="specialist_experience",
        ),
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


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    booking_id: Mapped[UUID] = mapped_column(ForeignKey("bookings.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_publish_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    __table_args__ = (
        CheckConstraint("kind IN ('booking_created', 'booking_cancelled')", name="outbox_kind"),
    )


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("outbox_events.id", ondelete="RESTRICT"), primary_key=True
    )
    channel: Mapped[str] = mapped_column(String(10), primary_key=True, default="email")
    status: Mapped[str] = mapped_column(String(10), default="pending")
    attempts: Mapped[int] = mapped_column(default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(50))
    __table_args__ = (
        CheckConstraint("channel = 'email'", name="notification_channel"),
        CheckConstraint(
            "status IN ('pending', 'retrying', 'sent', 'failed')", name="notification_status"
        ),
        CheckConstraint("attempts >= 0", name="notification_attempts"),
    )


class AIUsage(Base):
    __tablename__ = "ai_usage"
    day: Mapped[date] = mapped_column(primary_key=True)
    calls: Mapped[int] = mapped_column()
    __table_args__ = (CheckConstraint("calls > 0", name="ai_usage_positive_calls"),)
