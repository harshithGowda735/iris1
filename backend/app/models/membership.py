"""
NodeMembership model — maps users to nodes with a specific role.

The composite primary key ``(user_id, node_id)`` prevents duplicate
memberships.  The ``RoleEnum`` determines write-access to restricted
channels (e.g. BOARD tab).

Role ordering (lowest → highest privilege):
    MEMBER  <  CR  <  FACULTY  <  ADMIN
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.node import Node
    from app.models.profile import UserProfile


class RoleEnum(str, enum.Enum):
    """Privilege level within a node."""

    MEMBER = "MEMBER"
    CR = "CR"
    FACULTY = "FACULTY"
    ADMIN = "ADMIN"


# Ordered list used for privilege comparison — index encodes rank.
_ROLE_RANK: dict[RoleEnum, int] = {
    RoleEnum.MEMBER: 0,
    RoleEnum.CR: 1,
    RoleEnum.FACULTY: 2,
    RoleEnum.ADMIN: 3,
}


def role_gte(role: RoleEnum, minimum: RoleEnum) -> bool:
    """Return ``True`` if *role* is equal to or higher than *minimum*."""
    return _ROLE_RANK[role] >= _ROLE_RANK[minimum]


class NodeMembership(Base):
    """Association between a user and a node, carrying a role.

    A user may belong to many nodes (e.g. their section *and* their
    department).  Each membership independently records the user's
    role within that node.
    """

    __tablename__ = "node_memberships"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[RoleEnum] = mapped_column(
        Enum(RoleEnum, name="role_enum", native_enum=False),
        nullable=False,
        default=RoleEnum.MEMBER,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ── Relationships ────────────────────────────────────
    user: Mapped[UserProfile] = relationship("UserProfile", lazy="selectin")
    node: Mapped[Node] = relationship("Node", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Membership user={self.user_id} node={self.node_id} role={self.role.value}>"
