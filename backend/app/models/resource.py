"""
Resource model — academic files stored in a node's REPO channel.

Each resource is tagged with a ``subject_code`` (e.g. ``"21CS32"``)
so students can filter and browse materials by subject.  The actual
file blob lives in an external object store; this model tracks the
URL and metadata.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.node import Node
    from app.models.profile import UserProfile


class Resource(Base, UUIDMixin, TimestampMixin):
    """An uploaded academic file (notes, syllabus, lab manual, etc.)."""

    __tablename__ = "resources"

    node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploader_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    subject_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    # ── Relationships ────────────────────────────────────
    node: Mapped[Node] = relationship("Node", lazy="selectin")
    uploader: Mapped[UserProfile] = relationship("UserProfile", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Resource {self.file_name!r} subject={self.subject_code}>"
