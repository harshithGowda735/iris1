"""
Pydantic v2 schemas for the Node domain.

Defines request/response schemas for academic hierarchy nodes (COLLEGE,
DEPARTMENT, BATCH, SECTION) and recursive hierarchy traversal representations.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.node import NodeType

# ── Base & Mutation Schemas ──────────────────────────────


class NodeBase(BaseModel):
    """Common attributes shared across node schemas."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Display name of the organizational node (e.g. 'Computer Science')",
        examples=["Computer Science"],
    )
    type: NodeType = Field(
        ...,
        description="Hierarchical level within the academic institution",
        examples=[NodeType.DEPARTMENT],
    )
    parent_id: UUID | None = Field(
        default=None,
        description="UUID of the parent node (null for root COLLEGE nodes)",
    )


class NodeCreate(NodeBase):
    """Payload for creating a new node."""

    model_config = ConfigDict()


class NodeUpdate(BaseModel):
    """Payload for updating an existing node."""

    model_config = ConfigDict()

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="New display name of the node",
    )


# ── Response Schemas ─────────────────────────────────────


class NodeResponse(BaseModel):
    """Standard representation of an academic node."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique node identifier")
    name: str = Field(..., description="Node name")
    type: NodeType = Field(..., description="Node hierarchical level")
    parent_id: UUID | None = Field(default=None, description="Parent node UUID")
    created_at: datetime = Field(..., description="Timestamp when node was created")
    updated_at: datetime = Field(..., description="Timestamp when node was last updated")


# Backwards-compatibility alias for existing modules and tests
NodeRead = NodeResponse


class NodeBreadcrumb(BaseModel):
    """Ancestor representation in a tree traversal path."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Ancestor node identifier")
    name: str = Field(..., description="Ancestor node display name")
    type: NodeType = Field(..., description="Ancestor hierarchical level")


class NodeHierarchyResponse(BaseModel):
    """Full hierarchical context from Root down to the active node."""

    model_config = ConfigDict(from_attributes=True)

    node: NodeResponse = Field(
        ...,
        description="The active node being inspected",
    )
    breadcrumbs: list[NodeBreadcrumb] = Field(
        ...,
        description="Ordered list of ancestor breadcrumbs from Root down to current node",
    )


class NodeAncestorPath(BaseModel):
    """Ordered ancestor path from leaf to root."""

    model_config = ConfigDict(from_attributes=True)

    ancestors: list[NodeResponse] = Field(
        ...,
        description="Ordered ancestors from leaf up to root",
    )
