from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase): pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Telegram user IDs are 64-bit values and can exceed PostgreSQL INTEGER.
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(128))
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Expense(Base):
    __tablename__ = "expenses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="TJS")
    category: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str] = mapped_column(Text)
    spent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CategoryLimit(Base):
    __tablename__ = "category_limits"
    __table_args__ = (UniqueConstraint("user_id", "category", "period", name="uq_limit_user_category_period"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(64))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    period: Mapped[str] = mapped_column(String(10), default="month")


class WalletSettings(Base):
    __tablename__ = "wallet_settings"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    currency: Mapped[str] = mapped_column(String(3), default="TJS")


class Income(Base):
    __tablename__ = "incomes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class MonthlyBudget(Base):
    __tablename__ = "monthly_budgets"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    currency: Mapped[str] = mapped_column(String(3), primary_key=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class BotProfile(Base):
    __tablename__ = "bot_profiles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    language: Mapped[str] = mapped_column(String(2), default="ru")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    seen_version: Mapped[str] = mapped_column(String(32), default="")
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
