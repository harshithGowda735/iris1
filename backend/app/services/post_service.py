"""
Post service — channel-level access control, authoring, and feed pagination.

Key business rules:
- BOARD: Official announcements restricted to CR, FACULTY, or ADMIN (direct or inherited).
- CHAT: Open discussion stream available to all active members of the node or its ancestors.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.membership import NodeMembership, RoleEnum, role_gte
from app.models.post import Post, TabEnum
from app.models.profile import UserProfile
from app.schemas.post import ChannelTab, PostCreate
from app.services import node_service


class PostService:
    """Service layer managing post creation, tab permissions, and paginated feed retrieval."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _verify_channel_permission(
        self, user_id: UUID, node_id: UUID, tab: ChannelTab
    ) -> None:
        """Verify caller has appropriate membership privileges for the target tab.

        - CHAT requires active membership in node or its ancestors.
        - BOARD requires CR, FACULTY, or ADMIN in node or its ancestors.
        """
        # Ensure target node exists
        await node_service.get_node(self.db, node_id)

        # Retrieve full ancestor branch via recursive CTE
        breadcrumbs = await node_service.get_ancestor_path(self.db, node_id)
        ancestor_ids = [b.id for b in breadcrumbs]

        query = select(NodeMembership).where(
            NodeMembership.user_id == user_id,
            NodeMembership.node_id.in_(ancestor_ids),
        )
        memberships = list((await self.db.execute(query)).scalars().all())

        if not memberships:
            raise ForbiddenError("You are not a member of this node.")

        if tab == ChannelTab.BOARD:
            can_post_board = any(role_gte(m.role, RoleEnum.CR) for m in memberships)
            if not can_post_board:
                raise ForbiddenError(
                    "Only CR, FACULTY, or ADMIN members may post to the BOARD channel."
                )

    async def create_post(
        self, node_id: UUID, user: UserProfile, post_in: PostCreate
    ) -> Post:
        """Create a post on the specified node channel with strict permission enforcement."""
        tab_enum = TabEnum(post_in.tab.value if isinstance(post_in.tab, ChannelTab) else post_in.tab)
        await self._verify_channel_permission(user.id, node_id, ChannelTab(tab_enum.value))

        post = Post(
            node_id=node_id,
            author_id=user.id,
            tab=tab_enum,
            content=post_in.content,
        )
        self.db.add(post)
        await self.db.flush()
        await self.db.refresh(post)
        # Preload author details for immediate serialization
        await self.db.refresh(post, attribute_names=["author"])
        return post

    async def get_node_posts(
        self,
        node_id: UUID,
        tab: ChannelTab | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Post], int]:
        """Return an efficient paginated feed of posts for a node ordered by created_at desc."""
        # Ensure node exists
        await node_service.get_node(self.db, node_id)

        base_query = (
            select(Post)
            .where(Post.node_id == node_id)
            .options(selectinload(Post.author))
        )
        count_query = (
            select(func.count())
            .select_from(Post)
            .where(Post.node_id == node_id)
        )

        if tab is not None:
            tab_val = TabEnum(tab.value if isinstance(tab, ChannelTab) else tab)
            base_query = base_query.where(Post.tab == tab_val)
            count_query = count_query.where(Post.tab == tab_val)

        total = (await self.db.execute(count_query)).scalar_one()
        posts_result = await self.db.execute(
            base_query.order_by(Post.created_at.desc(), Post.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(posts_result.scalars().all()), total

    async def get_post(self, post_id: UUID) -> Post:
        """Fetch a single post by ID with preloaded author or raise NotFoundError."""
        query = select(Post).where(Post.id == post_id).options(selectinload(Post.author))
        post = (await self.db.execute(query)).scalar_one_or_none()
        if post is None:
            raise NotFoundError("Post", post_id)
        return post

    async def delete_post(self, post_id: UUID, requesting_user: UserProfile) -> None:
        """Delete a post.

        Allowed if requesting user is the original author OR holds CR+ on the node.
        """
        post = await self.get_post(post_id)

        if post.author_id != requesting_user.id:
            # Non-author: check elevated privileges
            breadcrumbs = await node_service.get_ancestor_path(self.db, post.node_id)
            ancestor_ids = [b.id for b in breadcrumbs]
            query = select(NodeMembership).where(
                NodeMembership.user_id == requesting_user.id,
                NodeMembership.node_id.in_(ancestor_ids),
            )
            memberships = list((await self.db.execute(query)).scalars().all())
            is_authorized = any(role_gte(m.role, RoleEnum.CR) for m in memberships)
            if not is_authorized:
                raise ForbiddenError("You can only delete your own posts.")

        await self.db.delete(post)
        await self.db.flush()


# ── Module-Level Delegates (Backwards-Compatibility) ──────


async def create_post(
    db: AsyncSession,
    payload: PostCreate,
    author: UserProfile,
) -> Post:
    target_node = payload.node_id
    if target_node is None:
        raise ValueError("node_id must be provided in payload or route.")
    return await PostService(db).create_post(target_node, author, payload)


async def list_posts(
    db: AsyncSession,
    node_id: UUID,
    tab: TabEnum | None = None,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Post], int]:
    channel_tab = ChannelTab(tab.value) if tab else None
    return await PostService(db).get_node_posts(node_id, channel_tab, limit=limit, offset=offset)


async def get_post(db: AsyncSession, post_id: UUID) -> Post:
    return await PostService(db).get_post(post_id)


async def delete_post(
    db: AsyncSession,
    post_id: UUID,
    requesting_user: UserProfile,
) -> None:
    await PostService(db).delete_post(post_id, requesting_user)
