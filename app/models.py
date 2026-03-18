from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    balance_tokens: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    balance_rmb: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    consumption_records: Mapped[list[ConsumptionRecord]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class ApiKeyMapping(Base):
    __tablename__ = "api_key_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_key: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    upstream_bearer_token: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ModelMapping(Base):
    __tablename__ = "model_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_name: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    upstream_model: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ConsumptionRecord(Base):
    __tablename__ = "consumption_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    endpoint: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    task_id: Mapped[Optional[str]] = mapped_column(String(128), index=True, nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)

    tokens_charged: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    amount_rmb: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    balance_before: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    balance_after: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)

    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    upstream_status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="consumption_records")


Index("ix_consumption_user_created", ConsumptionRecord.user_id, ConsumptionRecord.created_at)


class VideoTask(Base):
    __tablename__ = "video_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    task_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)

    public_model: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    upstream_model: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    has_video_input: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    charged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    charged_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    charged_amount_rmb: Mapped[Optional[float]] = mapped_column(Numeric(20, 6), nullable=True)
    charged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "task_id", name="uq_video_tasks_user_task"),)
