"""
Pydantic v2 schemas for the NodeMembership and Access Control domain.

Defines schemas for membership representations, node role assignments,
and student rosters with nested profile details.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.schemas.profile import ProfileResponse, RoleType


class MembershipBase(BaseModel):
    """Base fields representing node membership."""

    user_id: UUID = Field(..., description="UUID of the member user")
    node_id: UUID = Field(..., description="UUID of the associated organizational node")
    role: RoleType = Field(
        default=RoleType.MEMBER,
        description="Privilege role within the node (MEMBER, CR, FACULTY, ADMIN)",
    )


class MembershipCreate(MembershipBase):
    """Payload for creating or assigning a role to a user in a node."""

    model_config = ConfigDict()


class MembershipResponse(BaseModel):
    """Public representation of a node membership record."""

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID = Field(..., description="Member user UUID")
    node_id: UUID = Field(..., description="Node UUID")
    role: RoleType = Field(..., description="Role assigned in this node")
    created_at: datetime = Field(
        validation_alias=AliasChoices("created_at", "joined_at"),
        description="Timestamp when user joined the node",
    )


class MembershipWithProfile(BaseModel):
    """Membership record with embedded safe profile details for node rosters."""

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID = Field(..., description="Member user UUID")
    node_id: UUID = Field(..., description="Node UUID")
    role: RoleType = Field(..., description="Role assigned in this node")
    created_at: datetime = Field(
        validation_alias=AliasChoices("created_at", "joined_at"),
        description="Timestamp when user joined the node",
    )
    profile: ProfileResponse = Field(
        validation_alias=AliasChoices("profile", "user"),
        description="Safe profile details of the member",
    )
