"""
Node hierarchy endpoints — create, list, traverse, and hierarchy inspection.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user, require_node_role
from app.models.membership import NodeMembership
from app.models.profile import UserProfile
from app.schemas.membership import MembershipWithProfile
from app.schemas.node import (
    NodeAncestorPath,
    NodeCreate,
    NodeHierarchyResponse,
    NodeResponse,
    NodeUpdate,
)
from app.schemas.profile import RoleType
from app.services.node_service import NodeService, get_ancestor_nodes_leaf_to_root
from app.services.profile_service import ProfileService

router = APIRouter()


# ── Root & Collection Endpoints ──────────────────────────


@router.get(
    "/roots",
    response_model=list[NodeResponse],
    summary="Get all root-level college nodes",
    status_code=status.HTTP_200_OK,
)
async def get_root_nodes(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[NodeResponse]:
    """Retrieve all top-level institution nodes (parent_id IS NULL)."""
    service = NodeService(db)
    nodes = await service.get_root_nodes()
    return [NodeResponse.model_validate(n) for n in nodes]


@router.get(
    "",
    response_model=list[NodeResponse],
    summary="List root nodes or filter by parent_id",
    status_code=status.HTTP_200_OK,
)
async def list_nodes(
    db: Annotated[AsyncSession, Depends(get_db)],
    parent_id: Annotated[
        UUID | None,
        Query(description="Parent node UUID filter. If omitted, returns root colleges."),
    ] = None,
) -> list[NodeResponse]:
    """Return root college nodes (when parent_id is omitted) or direct children of the given parent."""
    service = NodeService(db)
    if parent_id is None:
        nodes = await service.get_root_nodes()
    else:
        nodes = await service.get_children_nodes(parent_id)
    return [NodeResponse.model_validate(n) for n in nodes]


@router.post(
    "",
    response_model=NodeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new node",
)
async def create_node(
    payload: NodeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[UserProfile, Depends(get_current_user)],
) -> NodeResponse:
    """Create a new node within the academic hierarchy.

    Hierarchy constraints are strictly enforced:
    - COLLEGE nodes must have no parent
    - DEPARTMENT nodes must have a COLLEGE parent
    - BATCH nodes must have a DEPARTMENT parent
    - SECTION nodes must have a BATCH parent
    """
    service = NodeService(db)
    node = await service.create_node(payload)
    return NodeResponse.model_validate(node)


# ── Traversal & Hierarchy Endpoints ──────────────────────


@router.get(
    "/{node_id}/children",
    response_model=list[NodeResponse],
    summary="Get direct sub-nodes",
    status_code=status.HTTP_200_OK,
)
async def get_children_nodes(
    node_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[NodeResponse]:
    """Fetch all direct sub-nodes under a given node (e.g. all sections in a batch)."""
    service = NodeService(db)
    children = await service.get_children_nodes(node_id)
    return [NodeResponse.model_validate(c) for c in children]


@router.get(
    "/{node_id}/hierarchy",
    response_model=NodeHierarchyResponse,
    summary="Get full hierarchy breadcrumbs from root to node",
    status_code=status.HTTP_200_OK,
)
async def get_node_hierarchy(
    node_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NodeHierarchyResponse:
    """Walk up the hierarchy via recursive CTE to return the active node alongside

    an ordered breadcrumb list from Root down to current node:
    [Campus Root -> Department -> Batch -> Section].
    """
    service = NodeService(db)
    return await service.get_hierarchy(node_id)


@router.get(
    "/{node_id}/ancestors",
    response_model=NodeAncestorPath,
    summary="Get leaf-to-root ancestor path",
    status_code=status.HTTP_200_OK,
)
async def get_node_ancestors(
    node_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NodeAncestorPath:
    """Return ordered ancestors from leaf up to root."""
    ancestors = await get_ancestor_nodes_leaf_to_root(db, node_id)
    return NodeAncestorPath(
        ancestors=[NodeResponse.model_validate(n) for n in ancestors]
    )


@router.get(
    "/{node_id}/members",
    response_model=list[MembershipWithProfile],
    summary="List all members of a node (class roster)",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_node_role(RoleType.MEMBER))],
)
async def get_node_members(
    node_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[NodeMembership]:
    """Retrieve all members enrolled in this organizational node.

    Accessible exclusively to authenticated users who hold an active membership
    in this node or who inherit administrative privileges from an ancestor node.
    Returns safe profile data with zero private contact fields.
    """
    profile_service = ProfileService(db)
    return await profile_service.get_node_members(node_id)


# ── Single Node CRUD Endpoints ───────────────────────────


@router.get(
    "/{node_id}",
    response_model=NodeResponse,
    summary="Get a single node by UUID",
    status_code=status.HTTP_200_OK,
)
async def get_node(
    node_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NodeResponse:
    """Fetch a single node by its UUID. Returns HTTP 404 if not found."""
    service = NodeService(db)
    node = await service.get_node(node_id)
    return NodeResponse.model_validate(node)


@router.patch(
    "/{node_id}",
    response_model=NodeResponse,
    summary="Update a node",
    status_code=status.HTTP_200_OK,
)
async def update_node(
    node_id: UUID,
    payload: NodeUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[UserProfile, Depends(get_current_user)],
) -> NodeResponse:
    """Apply a partial update to a node (name)."""
    service = NodeService(db)
    node = await service.update_node(node_id, payload)
    return NodeResponse.model_validate(node)


@router.delete(
    "/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
    summary="Delete a node and descendants",
)
async def delete_node(
    node_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[UserProfile, Depends(get_current_user)],
) -> None:
    """Delete a node and all its child descendants (via database CASCADE)."""
    service = NodeService(db)
    await service.delete_node(node_id)
