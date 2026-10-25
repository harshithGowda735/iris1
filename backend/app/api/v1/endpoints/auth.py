"""
Auth & Profile endpoints — user profile onboarding, `/me`, and membership lookup.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.membership import NodeMembership
from app.models.profile import UserProfile
from app.schemas.membership import MembershipResponse
from app.schemas.profile import ProfileCreate, ProfileResponse, ProfileUpdate
from app.services.profile_service import ProfileService

router = APIRouter()


@router.post(
    "/register",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new student or faculty profile",
)
async def register(
    payload: ProfileCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserProfile:
    """Create or link a `UserProfile` for a verified Supabase Auth user.

    Enforces roll number uniqueness and assigns the primary section.
    """
    service = ProfileService(db)
    return await service.get_or_create_profile(payload.id, payload)


@router.get(
    "/me",
    response_model=ProfileResponse,
    summary="Get current user's profile and section assignment",
    status_code=status.HTTP_200_OK,
)
async def get_me(
    user: Annotated[UserProfile, Depends(get_current_user)],
) -> UserProfile:
    """Return the authenticated caller's profile and assigned primary section."""
    return user


@router.patch(
    "/me",
    response_model=ProfileResponse,
    summary="Update current user's profile",
    status_code=status.HTTP_200_OK,
)
async def update_me(
    payload: ProfileUpdate,
    user: Annotated[UserProfile, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserProfile:
    """Update profile details (name, assigned primary section)."""
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.primary_section_id is not None:
        user.primary_section_id = payload.primary_section_id

    await db.flush()
    await db.refresh(user)
    return user


@router.get(
    "/me/memberships",
    response_model=list[MembershipResponse],
    summary="Get all nodes/classes the current user is a member of",
    status_code=status.HTTP_200_OK,
)
async def get_my_memberships(
    user: Annotated[UserProfile, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[NodeMembership]:
    """Return all organizational nodes (colleges, departments, batches, sections)

    where the authenticated user holds an active membership.
    """
    service = ProfileService(db)
    return await service.get_user_memberships(user.id)
