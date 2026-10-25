"""
Post model — content written to a node's CHAT or BOARD channel.

CHAT posts are ephemeral class discussion; BOARD posts are curated
announcements restricted to CR / FACULTY / ADMIN roles.  The service
layer enforces that restriction — the model itself is intentionally
role-agnostic.
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.node import Node
    from app.models.profile import UserProfile


class TabEnum(str, enum.Enum):
    """Target channel within a node."""

    CHAT = "CHAT"
    BOARD = "BOARD"


class Post(Base, UUIDMixin, TimestampMixin):
    """A single message or announcement posted to a node channel."""

    __tablename__ = "posts"

    node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tab: Mapped[TabEnum] = mapped_column(
        Enum(TabEnum, name="tab_enum", native_enum=False),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Relationships ────────────────────────────────────
    node: Mapped[Node] = relationship("Node", lazy="selectin")
    author: Mapped[UserProfile] = relationship("UserProfile", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Post {self.id} tab={self.tab.value} node={self.node_id}>"
