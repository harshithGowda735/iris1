"""
Profile & Membership service — identity lifecycle and node membership management.

Handles student/faculty onboarding with privacy-first profile fields,
membership queries, and node role assignments.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.models.membership import NodeMembership, RoleEnum
from app.models.node import Node
from app.models.profile import UserProfile
from app.schemas.profile import ProfileCreate, RoleType


class ProfileService:
    """Service layer for user profiles, roles, and node rosters."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_profile(self, user_id: UUID) -> UserProfile:
        """Fetch profile by UUID or raise NotFoundError."""
        profile = await self.db.get(UserProfile, user_id)
        if profile is None:
            raise NotFoundError("UserProfile", user_id)
        return profile

    async def get_or_create_profile(
        self, user_id: UUID, profile_data: ProfileCreate
    ) -> UserProfile:
        """Fetch existing profile by user_id, or create a new one.

        Ensures roll numbers are unique across the institution.
        """
        existing = await self.db.get(UserProfile, user_id)
        if existing is not None:
            return existing

        # Ensure roll number is not already assigned to another user
        dup_query = select(UserProfile).where(
            UserProfile.roll_number == profile_data.roll_number
        )
        dup = (await self.db.execute(dup_query)).scalar_one_or_none()
        if dup is not None:
            raise ConflictError(
                f"Roll number '{profile_data.roll_number}' is already registered."
            )

        # If primary section was provided, verify section node exists
        if profile_data.primary_section_id is not None:
            section = await self.db.get(Node, profile_data.primary_section_id)
            if section is None:
                raise NotFoundError("Node", profile_data.primary_section_id)

        profile = UserProfile(
            id=user_id,
            roll_number=profile_data.roll_number,
            full_name=profile_data.full_name,
            primary_section_id=profile_data.primary_section_id,
        )
        self.db.add(profile)

        # If assigned a primary section, automatically grant MEMBER membership
        if profile_data.primary_section_id is not None:
            membership = NodeMembership(
                user_id=user_id,
                node_id=profile_data.primary_section_id,
                role=RoleEnum.MEMBER,
            )
            self.db.add(membership)

        await self.db.flush()
        await self.db.refresh(profile)
        return profile

    async def get_user_memberships(self, user_id: UUID) -> list[NodeMembership]:
        """Fetch all node memberships for a given user."""
        query = (
            select(NodeMembership)
            .where(NodeMembership.user_id == user_id)
            .order_by(NodeMembership.joined_at.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def assign_node_role(
        self, user_id: UUID, node_id: UUID, role: RoleType | RoleEnum
    ) -> NodeMembership:
        """Assign or update a user's role within an organizational node."""
        user = await self.db.get(UserProfile, user_id)
        if user is None:
            raise NotFoundError("UserProfile", user_id)

        node = await self.db.get(Node, node_id)
        if node is None:
            raise NotFoundError("Node", node_id)

        role_enum = RoleEnum(role.value if isinstance(role, RoleType) else role)

        query = select(NodeMembership).where(
            NodeMembership.user_id == user_id,
            NodeMembership.node_id == node_id,
        )
        membership = (await self.db.execute(query)).scalar_one_or_none()

        if membership is not None:
            membership.role = role_enum
        else:
            membership = NodeMembership(
                user_id=user_id,
                node_id=node_id,
                role=role_enum,
            )
            self.db.add(membership)

        await self.db.flush()
        await self.db.refresh(membership)
        return membership

    async def get_node_members(self, node_id: UUID) -> list[NodeMembership]:
        """Fetch all members of a node with preloaded user profiles.

        Excludes private contact details by mapping to safe UserProfile entities.
        """
        node = await self.db.get(Node, node_id)
        if node is None:
            raise NotFoundError("Node", node_id)

        query = (
            select(NodeMembership)
            .where(NodeMembership.node_id == node_id)
            .options(selectinload(NodeMembership.user))
            .order_by(NodeMembership.joined_at.asc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())
