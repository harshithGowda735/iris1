"""
Pydantic v2 schemas for the UserProfile and Identity domain.

Privacy-first architecture: Profiles contain strictly institution-relevant fields
(roll_number, full_name, primary_section_id). Zero phone numbers, zero personal emails.
"""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ── Roles ────────────────────────────────────────────────


class RoleType(str, enum.Enum):
    """Institutional role hierarchy within a node."""

    MEMBER = "MEMBER"
    CR = "CR"
    FACULTY = "FACULTY"
    ADMIN = "ADMIN"


# ── Base & Mutation Schemas ──────────────────────────────


class ProfileBase(BaseModel):
    """Common fields for user profile identification."""

    roll_number: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Institutional student/faculty roll number or employee ID",
        examples=["1AY21CS001"],
    )
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Full display name",
        examples=["Ada Lovelace"],
    )


class ProfileCreate(ProfileBase):
    """Payload for onboarding / registering a new user profile.

    ``id`` corresponds directly to the Supabase Auth UID (`sub` claim)
    to maintain a strict 1-to-1 mapping with the auth provider.
    """

    model_config = ConfigDict()

    id: UUID = Field(
        ...,
        description="Supabase Auth UID matching JWT 'sub' claim",
    )
    primary_section_id: UUID | None = Field(
        default=None,
        description="UUID of the student's assigned section node",
    )


class ProfileUpdate(BaseModel):
    """Payload for updating an existing user profile."""

    model_config = ConfigDict()

    full_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated full name",
    )
    primary_section_id: UUID | None = Field(
        default=None,
        description="Updated primary section node UUID",
    )


# ── Response Schemas ─────────────────────────────────────


class ProfileResponse(BaseModel):
    """Safe public representation of a user profile.

    Strict privacy enforcement: Excludes all personal contact information.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="User unique identifier (Supabase Auth UID)")
    roll_number: str = Field(..., description="Institutional roll number")
    full_name: str = Field(..., description="User full display name")
    primary_section_id: UUID | None = Field(
        default=None,
        description="Assigned primary academic section",
    )
    created_at: datetime | None = Field(
        default=None,
        description="Timestamp of profile creation",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="Timestamp of last profile update",
    )


# Backward-compatibility alias for existing modules/tests
ProfileRead = ProfileResponse
