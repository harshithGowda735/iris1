"""
Pydantic v2 schemas for the Posts domain (CHAT vs. BOARD channels).
"""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── Channel Tabs ─────────────────────────────────────────


class ChannelTab(str, enum.Enum):
    """Target communication channel within an academic node.

    - CHAT: Open discussion stream for all verified node members.
    - BOARD: Official announcements restricted to CR, FACULTY, and ADMIN.
    """

    CHAT = "CHAT"
    BOARD = "BOARD"


# Backwards compatibility alias
TabEnum = ChannelTab


# ── Author Summary ───────────────────────────────────────


class PostAuthorSummary(BaseModel):
    """Safe author representation attached to posts without exposing contact details."""

    model_config = ConfigDict(from_attributes=True)

    full_name: str = Field(..., description="Author full name")
    roll_number: str = Field(..., description="Author institutional roll number")


# ── Base & Mutation Schemas ──────────────────────────────


class PostBase(BaseModel):
    """Base fields for node messages and announcements."""

    content: str = Field(
        ...,
        min_length=1,
        max_length=10_000,
        description="Markdown message content",
        examples=["**Exam postponed** to Monday at 10:00 AM."],
    )
    tab: ChannelTab = Field(
        default=ChannelTab.CHAT,
        description="Target channel: CHAT (open) or BOARD (curated announcements)",
    )

    @field_validator("content")
    @classmethod
    def _strip_content(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Post content must not be blank.")
        return stripped


class PostCreate(PostBase):
    """Payload for creating a post on a node channel."""

    model_config = ConfigDict()

    # Optional in payload when supplied via path parameter /nodes/{node_id}/posts
    node_id: UUID | None = Field(
        default=None,
        description="UUID of the target node (optional when node_id is in URL path)",
    )


# ── Response Schemas ─────────────────────────────────────


class PostResponse(BaseModel):
    """Public representation of a posted message or announcement."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique post identifier")
    node_id: UUID = Field(..., description="Associated node UUID")
    author_id: UUID = Field(..., description="Author UserProfile UUID")
    tab: ChannelTab = Field(..., description="Channel tab (CHAT or BOARD)")
    content: str = Field(..., description="Markdown post body")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime | None = Field(default=None, description="Last updated timestamp")
    author: PostAuthorSummary | None = Field(
        default=None,
        description="Author summary profile (full_name, roll_number)",
    )


# Backward-compatibility alias
PostRead = PostResponse


class PostPagination(BaseModel):
    """Paginated list of posts with metadata."""

    model_config = ConfigDict(from_attributes=True)

    items: list[PostResponse] = Field(..., description="List of posts in the requested window")
    total: int = Field(..., description="Total posts matching filter")
    limit: int = Field(default=50, description="Items per page limit")
    offset: int = Field(default=0, description="Page offset")


# Backward-compatibility alias
PostList = PostPagination
