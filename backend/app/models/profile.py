"""
UserProfile model — the privacy-first identity anchor.

Profiles are keyed by the same UUID issued by Supabase Auth (``id``),
storing only the institution-relevant data: roll number, full name,
and the user's primary section assignment.  **No phone numbers, no
personal emails.**
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.node import Node


class UserProfile(Base, UUIDMixin, TimestampMixin):
    """A student or faculty member registered in IRIS.

    ``id`` is synchronised with the Supabase Auth UID so there is a
    single, consistent identity across authentication and application
    data.
    """

    __tablename__ = "user_profiles"

    roll_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    primary_section_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("nodes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Relationships ────────────────────────────────────
    primary_section: Mapped[Node | None] = relationship(
        "Node",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<UserProfile {self.roll_number}: {self.full_name!r}>"
