"""Ma'lumotlar bazasi modellari."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    true,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Barcha vaqtlar UTC (timezone'siz) saqlanadi — SQLite va PostgreSQL uchun bir xil."""
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class DriverStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class OrderStatus(StrEnum):
    SEARCHING = "searching"
    ACCEPTED = "accepted"  # haydovchi yo'lda
    ARRIVED = "arrived"  # haydovchi kutmoqda
    IN_PROGRESS = "in_progress"  # safar davom etmoqda
    FINISHING = "finishing"  # yo'lovchi tasdig'i kutilmoqda
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_DRIVERS = "no_drivers"


ACTIVE_STATUSES = (
    OrderStatus.SEARCHING,
    OrderStatus.ACCEPTED,
    OrderStatus.ARRIVED,
    OrderStatus.IN_PROGRESS,
    OrderStatus.FINISHING,
)
DRIVER_ACTIVE_STATUSES = (
    OrderStatus.ACCEPTED,
    OrderStatus.ARRIVED,
    OrderStatus.IN_PROGRESS,
    OrderStatus.FINISHING,
)


class OfferStatus(StrEnum):
    SENT = "sent"
    DECLINED = "declined"
    ACCEPTED = "accepted"
    WITHDRAWN = "withdrawn"  # buyurtma olindi/bekor qilindi — xabar o'chirildi
    DRIVER_CANCELLED = "driver_cancelled"


class Passenger(Base):
    __tablename__ = "passengers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(128), default="")
    phone: Mapped[str | None] = mapped_column(String(32))
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    trips_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Driver(Base):
    __tablename__ = "drivers"
    __table_args__ = (
        Index("ix_drivers_dispatch", "is_online", "status", "lat", "lon"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(128), default="")
    phone: Mapped[str | None] = mapped_column(String(32))
    car_model: Mapped[str] = mapped_column(String(64), default="")
    car_color: Mapped[str] = mapped_column(String(32), default="")
    car_plate: Mapped[str] = mapped_column(String(16), default="")
    status: Mapped[str] = mapped_column(String(16), default=DriverStatus.PENDING)

    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    loc_accuracy: Mapped[float | None] = mapped_column(Float)
    loc_heading: Mapped[int | None] = mapped_column(Integer)
    loc_is_live: Mapped[bool] = mapped_column(Boolean, default=False)
    loc_updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    loc_valid_until: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    loc_reminded: Mapped[bool] = mapped_column(Boolean, default=False)

    current_order_id: Mapped[int | None] = mapped_column(Integer)
    balance: Mapped[int] = mapped_column(BigInteger, default=0)
    rating_sum: Mapped[int] = mapped_column(Integer, default=0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[float] = mapped_column(Float, default=4.7, index=True)
    trips_count: Mapped[int] = mapped_column(Integer, default=0)
    cancel_count: Mapped[int] = mapped_column(Integer, default=0)
    navigator: Mapped[str] = mapped_column(String(16), default="yandex")  # safar boshlanganda ochiladi
    # 🏡 "Uyga" rejimi: faqat uy tomonga ketayotgan buyurtmalar
    home_mode: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    home_lat: Mapped[float | None] = mapped_column(Float)
    home_lon: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    passenger_id: Mapped[int] = mapped_column(ForeignKey("passengers.id"), index=True)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default=OrderStatus.SEARCHING, index=True)
    search_round: Mapped[int] = mapped_column(Integer, default=1)
    wave: Mapped[int] = mapped_column(Integer, default=0)

    pickup_lat: Mapped[float] = mapped_column(Float)
    pickup_lon: Mapped[float] = mapped_column(Float)
    pickup_accuracy: Mapped[float | None] = mapped_column(Float)
    dest_lat: Mapped[float | None] = mapped_column(Float)
    dest_lon: Mapped[float | None] = mapped_column(Float)
    dest_title: Mapped[str | None] = mapped_column(String(128))
    comment: Mapped[str | None] = mapped_column(Text)

    est_distance_m: Mapped[int | None] = mapped_column(Integer)
    est_duration_s: Mapped[int | None] = mapped_column(Integer)
    est_price: Mapped[int | None] = mapped_column(Integer)
    pickup_eta_s: Mapped[int | None] = mapped_column(Integer)

    # Taksometr
    trip_distance_m: Mapped[float] = mapped_column(Float, default=0.0)
    track_lat: Mapped[float | None] = mapped_column(Float)
    track_lon: Mapped[float | None] = mapped_column(Float)
    track_at: Mapped[datetime | None] = mapped_column(DateTime)
    start_lat: Mapped[float | None] = mapped_column(Float)
    start_lon: Mapped[float | None] = mapped_column(Float)

    final_price: Mapped[int | None] = mapped_column(Integer)
    wait_charge: Mapped[int | None] = mapped_column(Integer)
    commission: Mapped[int | None] = mapped_column(Integer)
    auto_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    rating: Mapped[int | None] = mapped_column(Integer)
    cancelled_by: Mapped[str | None] = mapped_column(String(16))
    cancel_reason: Mapped[str | None] = mapped_column(String(64))
    call_count: Mapped[int] = mapped_column(Integer, default=0)
    near_notified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    rider_phone: Mapped[str | None] = mapped_column(String(32))  # boshqa odam uchun buyurtma
    # «📞 Aloqa»: kompaniya raqamiga qo'ng'iroqdagi qo'shimcha kodlar (yo'lovchi → haydovchi, haydovchi → yo'lovchi)
    call_code_p: Mapped[str | None] = mapped_column(String(8), index=True)
    call_code_d: Mapped[str | None] = mapped_column(String(8), index=True)
    # Yo'lovchining jonli joylashuvi (faqat shu buyurtma davomida, haydovchi uni topishi uchun)
    pax_lat: Mapped[float | None] = mapped_column(Float)
    pax_lon: Mapped[float | None] = mapped_column(Float)
    pax_accuracy: Mapped[float | None] = mapped_column(Float)
    pax_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Telegram xabarlari (kartalar)
    passenger_msg_id: Mapped[int | None] = mapped_column(BigInteger)
    passenger_live_msg_id: Mapped[int | None] = mapped_column(BigInteger)
    driver_msg_id: Mapped[int | None] = mapped_column(BigInteger)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    search_started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime)
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finish_requested_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)

    @property
    def has_destination(self) -> bool:
        return self.dest_lat is not None and self.dest_lon is not None


class OrderOffer(Base):
    __tablename__ = "order_offers"
    __table_args__ = (Index("ix_offers_order_driver", "order_id", "driver_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    search_round: Mapped[int] = mapped_column(Integer, default=1)
    wave: Mapped[int] = mapped_column(Integer, default=0)
    distance_m: Mapped[int] = mapped_column(Integer, default=0)
    eta_s: Mapped[int] = mapped_column(Integer, default=0)
    message_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), default=OfferStatus.SENT, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Transaction(Base):
    """Haydovchi balansi bo'yicha har bir harakat (ledger)."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)  # +to'ldirish / -komissiya
    balance_after: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(16))  # commission | topup | payment | bonus | adjust
    order_id: Mapped[int | None] = mapped_column(Integer)
    external_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class SavedPlace(Base):
    """Yo'lovchining saqlangan manzillari: 🏠 Uy, 🏢 Ish, 📌 boshqa."""

    __tablename__ = "saved_places"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    passenger_id: Mapped[int] = mapped_column(ForeignKey("passengers.id"), index=True)
    kind: Mapped[str] = mapped_column(String(8))  # home | work | other
    title: Mapped[str] = mapped_column(String(64))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class FavoriteDriver(Base):
    """❤️ Sevimli haydovchi — yo'lovchining buyurtmasi avval unga ko'rinadi."""

    __tablename__ = "favorite_drivers"
    __table_args__ = (UniqueConstraint("passenger_id", "driver_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    passenger_id: Mapped[int] = mapped_column(ForeignKey("passengers.id"), index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class BotUser(Base):
    """Bitta bot rejimida foydalanuvchining tanlagan roli."""

    __tablename__ = "bot_users"

    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    role: Mapped[str | None] = mapped_column(String(16))
    phone: Mapped[str | None] = mapped_column(String(32))  # ilovadan ro'yxatdan o'tish uchun tasdiqlangan raqam
    # Ilovada jonli joylashuv: standart yoqilgan, foydalanuvchi o'zi o'chirmaguncha ishlaydi
    live_share: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    # Ilova ko'rinishi: None/auto — Telegram mavzusi bo'yicha, light — kun, dark — tun
    theme: Mapped[str | None] = mapped_column(String(8))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
