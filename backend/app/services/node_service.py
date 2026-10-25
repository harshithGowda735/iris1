"""
Node service — hierarchy traversal and CRUD.

Provides the `NodeService` class for managing academic hierarchy structures:
COLLEGE -> DEPARTMENT -> BATCH -> SECTION.

Includes recursive CTE tree traversal to retrieve ancestor paths from Root down to
leaf nodes in a single SQL query round-trip.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.node import Node, NodeType
from app.schemas.node import (
    NodeBreadcrumb,
    NodeCreate,
    NodeHierarchyResponse,
    NodeResponse,
    NodeUpdate,
)

# Parent type constraint — a DEPARTMENT must sit under a COLLEGE, etc.
_VALID_PARENT_TYPE: dict[NodeType, NodeType | None] = {
    NodeType.COLLEGE: None,
    NodeType.DEPARTMENT: NodeType.COLLEGE,
    NodeType.BATCH: NodeType.DEPARTMENT,
    NodeType.SECTION: NodeType.BATCH,
}


class NodeService:
    """Service layer encapsulating node hierarchy operations and recursive traversal."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_node_by_id(self, node_id: UUID) -> Node | None:
        """Fetch a single node by its UUID, or return None if not found."""
        return await self.db.get(Node, node_id)

    async def get_node(self, node_id: UUID) -> Node:
        """Fetch a single node by its UUID, or raise NotFoundError."""
        node = await self.get_node_by_id(node_id)
        if node is None:
            raise NotFoundError("Node", node_id)
        return node

    async def get_root_nodes(self) -> list[Node]:
        """Fetch top-level college nodes (where parent_id IS NULL)."""
        query = select(Node).where(Node.parent_id.is_(None)).order_by(Node.name)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_children_nodes(self, node_id: UUID) -> list[Node]:
        """Fetch all direct sub-nodes under a given parent node."""
        # Ensure parent exists; raises NotFoundError if absent
        await self.get_node(node_id)
        query = select(Node).where(Node.parent_id == node_id).order_by(Node.name)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_ancestor_path(self, node_id: UUID) -> list[NodeBreadcrumb]:
        """Walk the hierarchy from current node up to root using a single recursive CTE.

        Returns an ordered list of breadcrumbs from Root down to the current node:
        [Root College -> Department -> Batch -> Section].
        """
        # Ensure node exists before traversal
        await self.get_node(node_id)

        # 1. Base / Anchor member: starting at the requested node with depth = 0
        anchor = (
            select(
                Node.id,
                Node.name,
                Node.type,
                Node.parent_id,
                literal(0).label("depth"),
            )
            .where(Node.id == node_id)
            .cte(name="ancestor_tree", recursive=True)
        )

        # 2. Recursive member: join parent on parent_id, incrementing depth
        parent_alias = aliased(Node, name="parent_node")
        recursive = select(
            parent_alias.id,
            parent_alias.name,
            parent_alias.type,
            parent_alias.parent_id,
            (anchor.c.depth + 1).label("depth"),
        ).join(anchor, anchor.c.parent_id == parent_alias.id)

        # 3. Union anchor and recursive members
        ancestors_cte = anchor.union_all(recursive)

        # 4. Order by depth DESC: Root (highest depth) down to current node (depth 0)
        query = select(
            ancestors_cte.c.id,
            ancestors_cte.c.name,
            ancestors_cte.c.type,
        ).order_by(ancestors_cte.c.depth.desc())

        result = await self.db.execute(query)
        rows = result.all()

        return [
            NodeBreadcrumb(id=row.id, name=row.name, type=row.type)
            for row in rows
        ]

    async def get_hierarchy(self, node_id: UUID) -> NodeHierarchyResponse:
        """Return the active node alongside its root-to-current breadcrumb path."""
        node = await self.get_node(node_id)
        breadcrumbs = await self.get_ancestor_path(node_id)
        return NodeHierarchyResponse(
            node=NodeResponse.model_validate(node),
            breadcrumbs=breadcrumbs,
        )

    async def create_node(self, payload: NodeCreate) -> Node:
        """Create a node, strictly enforcing academic hierarchy invariants."""
        expected_parent = _VALID_PARENT_TYPE[payload.type]

        if expected_parent is None:
            # COLLEGE nodes must not have a parent.
            if payload.parent_id is not None:
                raise BadRequestError("A COLLEGE node must not have a parent.")
        else:
            if payload.parent_id is None:
                raise BadRequestError(
                    f"A {payload.type.value} node requires a parent of type {expected_parent.value}."
                )
            parent = await self.db.get(Node, payload.parent_id)
            if parent is None:
                raise NotFoundError("Node", payload.parent_id)
            if parent.type != expected_parent:
                raise BadRequestError(
                    f"A {payload.type.value} node must be placed under a "
                    f"{expected_parent.value}, not a {parent.type.value}."
                )

        # Prevent duplicate sibling names under the same parent
        dup_query = select(Node).where(
            Node.parent_id == payload.parent_id,
            Node.name == payload.name,
        )
        existing = (await self.db.execute(dup_query)).scalar_one_or_none()
        if existing is not None:
            raise ConflictError(
                f"A node named '{payload.name}' already exists under the same parent."
            )

        node = Node(
            name=payload.name,
            type=payload.type,
            parent_id=payload.parent_id,
        )
        self.db.add(node)
        await self.db.flush()
        await self.db.refresh(node)
        return node

    async def update_node(self, node_id: UUID, payload: NodeUpdate) -> Node:
        """Apply a partial update to a node."""
        node = await self.get_node(node_id)

        if payload.name is not None:
            # Re-check uniqueness among siblings
            dup_query = select(Node).where(
                Node.parent_id == node.parent_id,
                Node.name == payload.name,
                Node.id != node.id,
            )
            if (await self.db.execute(dup_query)).scalar_one_or_none() is not None:
                raise ConflictError(
                    f"A sibling node named '{payload.name}' already exists."
                )
            node.name = payload.name

        await self.db.flush()
        await self.db.refresh(node)
        return node

    async def delete_node(self, node_id: UUID) -> None:
        """Delete a node and all its descendants (cascading)."""
        node = await self.get_node(node_id)
        await self.db.delete(node)
        await self.db.flush()


# ── Module-Level Delegates (Backwards-Compatibility) ──────


async def get_node(db: AsyncSession, node_id: UUID) -> Node:
    return await NodeService(db).get_node(node_id)


async def get_node_by_id(db: AsyncSession, node_id: UUID) -> Node | None:
    return await NodeService(db).get_node_by_id(node_id)


async def get_root_nodes(db: AsyncSession) -> list[Node]:
    return await NodeService(db).get_root_nodes()


async def get_children_nodes(db: AsyncSession, node_id: UUID) -> list[Node]:
    return await NodeService(db).get_children_nodes(node_id)


async def list_children(db: AsyncSession, parent_id: UUID | None) -> list[Node]:
    if parent_id is None:
        return await NodeService(db).get_root_nodes()
    return await NodeService(db).get_children_nodes(parent_id)


async def get_ancestor_path(db: AsyncSession, node_id: UUID) -> list[NodeBreadcrumb]:
    return await NodeService(db).get_ancestor_path(node_id)


async def get_ancestor_nodes_leaf_to_root(db: AsyncSession, node_id: UUID) -> list[Node]:
    """Retrieve full Node entities ordered from leaf to root (for backward compatibility)."""
    node = await NodeService(db).get_node(node_id)
    ordered = [node]
    current = node
    while current.parent_id is not None:
        parent = await NodeService(db).get_node_by_id(current.parent_id)
        if parent is None:
            break
        ordered.append(parent)
        current = parent
    return ordered


async def create_node(db: AsyncSession, payload: NodeCreate) -> Node:
    return await NodeService(db).create_node(payload)


async def update_node(db: AsyncSession, node_id: UUID, payload: NodeUpdate) -> Node:
    return await NodeService(db).update_node(node_id, payload)


async def delete_node(db: AsyncSession, node_id: UUID) -> None:
    await NodeService(db).delete_node(node_id)
