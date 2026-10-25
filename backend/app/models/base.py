"""
Declarative base & shared column mixins for all IRIS models.

Every table in the system inherits from ``Base`` which in turn uses
``UUIDMixin`` (provides a UUID primary key) and ``TimestampMixin``
(provides ``created_at`` / ``updated_at`` server-defaulted columns).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base for the IRIS schema."""


class UUIDMixin:
    """Provides a UUID v4 primary key column named ``id``."""

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    """Provides ``created_at`` and ``updated_at`` server-defaulted columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
