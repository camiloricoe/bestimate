"""SQLAlchemy models for scrape tracking."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Property(Base):
    """Queue of properties to scrape."""

    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    state: Mapped[str] = mapped_column(String(2), nullable=False, default="")
    zip_code: Mapped[str] = mapped_column(String(5), nullable=False, default="")

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )
    # pending | queued | in_progress | completed | failed | blocked

    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    zpid: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Result(Base):
    """Successful scrape results."""

    __tablename__ = "results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    zpid: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    zestimate: Mapped[float | None] = mapped_column(Float)
    price: Mapped[float | None] = mapped_column(Float)
    beds: Mapped[int | None] = mapped_column(Integer)
    baths: Mapped[float | None] = mapped_column(Float)
    sqft: Mapped[int | None] = mapped_column(Integer)
    lot_size_sqft: Mapped[float | None] = mapped_column(Float)
    year_built: Mapped[int | None] = mapped_column(Integer)
    property_type: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    city: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    state: Mapped[str] = mapped_column(String(2), nullable=False, default="")
    zip_code: Mapped[str] = mapped_column(String(5), nullable=False, default="")
    raw_data: Mapped[dict | None] = mapped_column(JSONB)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProxyHealth(Base):
    """Proxy health tracking."""

    __tablename__ = "proxy_health"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proxy_url: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    tier: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
