"""
FastAPI dependencies shared across endpoints.

Provides:
- `get_current_user`: Resolves incoming Bearer JWT tokens to a verified `UserProfile`.
- `require_node_role`: Enforces role-based access control with downward hierarchy inheritance
  (e.g., ADMIN at Department level inherits authority over all child Batches and Sections).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.models.membership import NodeMembership, RoleEnum, role_gte
from app.models.profile import UserProfile
from app.schemas.profile import RoleType
from app.services import node_service


async def get_current_user(
    authorization: Annotated[str | None, Header(description="Bearer <Supabase-JWT>")] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> UserProfile:
    """Resolve and verify the incoming Supabase JWT bearer token to a `UserProfile`.

    Verification workflow:
    1. Validates `Authorization: Bearer <token>` header format.
    2. Decodes JWT and verifies HS256 signature using `settings.jwt_secret`.
    3. Extracts `sub` claim (Supabase Auth UID).
    4. Queries database for the corresponding `UserProfile`.

    Raises
    ------
    UnauthorizedError (HTTP 401)
        If token is missing, malformed, expired, invalid, or profile is not found.
    """
    if not authorization:
        raise UnauthorizedError("Missing Authorization header.")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UnauthorizedError("Authorization header must be formatted as: Bearer <token>")

    # Decode and verify token signature and expiry via security module
    auth_uid = decode_access_token(token)

    profile = await db.get(UserProfile, auth_uid)
    if profile is None:
        raise UnauthorizedError(
            "No profile found for authenticated user. Complete registration first."
        )
    return profile


def require_node_role(min_role: RoleType | RoleEnum):
    """Dependency factory enforcing that the caller holds at least `min_role`

    on `node_id` (or inherits ADMIN/superior privileges from a parent node).

    Usage:
        @router.post(
            "/{node_id}/announcements",
            dependencies=[Depends(require_node_role(RoleType.CR))],
        )
    """

    async def _role_guard(
        node_id: Annotated[UUID, Path(description="UUID of the organizational node")],
        db: Annotated[AsyncSession, Depends(get_db)],
        user: Annotated[UserProfile, Depends(get_current_user)],
    ) -> NodeMembership:
        # 1. Retrieve all ancestors from current node up to root college in single CTE query
        breadcrumbs = await node_service.get_ancestor_path(db, node_id)
        ancestor_ids = [b.id for b in breadcrumbs]

        # 2. Fetch all memberships the user holds anywhere along this hierarchical branch
        stmt = select(NodeMembership).where(
            NodeMembership.user_id == user.id,
            NodeMembership.node_id.in_(ancestor_ids),
        )
        memberships = list((await db.execute(stmt)).scalars().all())

        if not memberships:
            raise ForbiddenError(
                f"User is not a member of this node hierarchy. Requires {min_role.value} privilege."
            )

        # 3. Direct check: user has explicit membership on target node with sufficient role
        direct = next((m for m in memberships if m.node_id == node_id), None)
        if direct and role_gte(direct.role, min_role):
            return direct

        # 4. Hierarchy inheritance check:
        # An ADMIN at an ancestor node (e.g. Department) cascades authority to all descendants
        admin_ancestor = next(
            (m for m in memberships if m.node_id != node_id and role_gte(m.role, RoleEnum.ADMIN)),
            None,
        )
        if admin_ancestor:
            return admin_ancestor

        # Check if an ancestor role satisfies min_role (e.g. FACULTY assigned at Department level)
        superior_ancestor = next(
            (m for m in memberships if m.node_id != node_id and role_gte(m.role, min_role)),
            None,
        )
        if superior_ancestor:
            return superior_ancestor

        raise ForbiddenError(
            f"Access denied: Requires at least {min_role.value} privilege on node '{node_id}'."
        )

    return _role_guard
