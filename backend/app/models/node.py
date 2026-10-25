"""
Node model — the fundamental building block of the IRIS hierarchy.

Nodes form a directed tree:  COLLEGE → DEPARTMENT → BATCH → SECTION.
The ``parent_id`` self-referential FK encodes the edge, while the
``NodeType`` enum constrains valid depth levels.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class NodeType(str, enum.Enum):
    """Hierarchical level of a node in the institution tree."""

    COLLEGE = "COLLEGE"
    DEPARTMENT = "DEPARTMENT"
    BATCH = "BATCH"
    SECTION = "SECTION"


class Node(Base, UUIDMixin, TimestampMixin):
    """An organisational unit within an institution's hierarchy.

    Examples
    --------
    - *College*:   ``Node(name="Dr. AIT", type=NodeType.COLLEGE)``
    - *Section*:   ``Node(name="Section B", type=NodeType.SECTION, parent_id=<batch_id>)``
    """

    __tablename__ = "nodes"
    __table_args__ = (
        UniqueConstraint("parent_id", "name", name="uq_node_parent_name"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[NodeType] = mapped_column(
        Enum(NodeType, name="node_type", native_enum=False),
        nullable=False,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # ── Relationships ────────────────────────────────────
    parent: Mapped[Node | None] = relationship(
        "Node",
        remote_side="Node.id",
        back_populates="children",
        lazy="selectin",
    )
    children: Mapped[list[Node]] = relationship(
        "Node",
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Node {self.type.value}: {self.name!r}>"
