"""
Post endpoints — CHAT and BOARD content delivery for academic nodes.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user, require_node_role
from app.models.profile import UserProfile
from app.schemas.post import ChannelTab, PostCreate, PostPagination, PostResponse
from app.schemas.profile import RoleType
from app.services.post_service import PostService

# ── Primary Node-Scoped Router (/nodes/{node_id}/posts) ──
router = APIRouter()


@router.get(
    "",
    response_model=PostPagination,
    summary="Get paginated posts for a node channel",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_node_role(RoleType.MEMBER))],
)
async def get_node_posts(
    node_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    tab: Annotated[ChannelTab | None, Query(description="Filter by CHAT or BOARD")] = None,
    limit: Annotated[int, Query(ge=1, le=200, description="Items per page")] = 50,
    offset: Annotated[int, Query(ge=0, description="Offset")] = 0,
) -> PostPagination:
    """Retrieve paginated posts for a node's CHAT or BOARD tab.

    Accessible to any active member of the node or its ancestors.
    """
    service = PostService(db)
    items, total = await service.get_node_posts(node_id, tab, limit=limit, offset=offset)
    return PostPagination(
        items=[PostResponse.model_validate(p) for p in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new post or announcement",
)
async def create_node_post(
    node_id: UUID,
    payload: PostCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserProfile, Depends(get_current_user)],
) -> PostResponse:
    """Post a message to a node channel.

    Channel access rules:
    - CHAT: Open to all verified node members.
    - BOARD: Restricted to CR, FACULTY, or ADMIN (direct or inherited).
    """
    service = PostService(db)
    post = await service.create_post(node_id, user, payload)
    return PostResponse.model_validate(post)


# ── Global & Legacy Collection Router (/posts) ───────────
legacy_router = APIRouter()


@legacy_router.post(
    "",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a post (legacy endpoint)",
)
async def legacy_create_post(
    payload: PostCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserProfile, Depends(get_current_user)],
) -> PostResponse:
    target_node = payload.node_id
    if target_node is None:
        raise ValueError("node_id is required in request body for this endpoint.")
    service = PostService(db)
    post = await service.create_post(target_node, user, payload)
    return PostResponse.model_validate(post)


@legacy_router.get(
    "",
    response_model=PostPagination,
    summary="List posts (legacy endpoint)",
)
async def legacy_list_posts(
    node_id: Annotated[UUID, Query(description="Node UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    tab: Annotated[ChannelTab | None, Query(description="Tab filter")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PostPagination:
    service = PostService(db)
    items, total = await service.get_node_posts(node_id, tab, limit=limit, offset=offset)
    return PostPagination(
        items=[PostResponse.model_validate(p) for p in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@legacy_router.get(
    "/{post_id}",
    response_model=PostResponse,
    summary="Get single post by UUID",
    status_code=status.HTTP_200_OK,
)
async def get_single_post(
    post_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PostResponse:
    service = PostService(db)
    post = await service.get_post(post_id)
    return PostResponse.model_validate(post)


@legacy_router.delete(
    "/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
    summary="Delete a post",
)
async def delete_post(
    post_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserProfile, Depends(get_current_user)],
) -> None:
    service = PostService(db)
    await service.delete_post(post_id, user)
