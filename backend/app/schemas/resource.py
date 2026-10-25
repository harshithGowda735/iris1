"""
Pydantic v2 schemas for the Resource (Academic REPO) domain.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── Base & Mutation Schemas ──────────────────────────────


class ResourceBase(BaseModel):
    """Base fields for academic resources (notes, syllabus, lab manuals)."""

    file_name: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Original name of the uploaded file",
        examples=["Module_1_DBMS_Notes.pdf"],
    )
    file_url: str = Field(
        ...,
        min_length=1,
        description="Public or storage URL of the file blob",
    )
    subject_code: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Institutional academic subject code",
        examples=["21CS32"],
    )

    @field_validator("subject_code")
    @classmethod
    def _uppercase_subject(cls, v: str) -> str:
        return v.strip().upper()


class ResourceCreate(ResourceBase):
    """Payload for indexing a newly uploaded academic file."""

    model_config = ConfigDict()

    # Optional in payload when supplied via path parameter /nodes/{node_id}/resources
    node_id: UUID | None = Field(
        default=None,
        description="UUID of the target node (optional when node_id is in URL path)",
    )


# ── Response Schemas ─────────────────────────────────────


class ResourceResponse(BaseModel):
    """Public representation of an academic resource."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique resource identifier")
    node_id: UUID = Field(..., description="Associated node UUID")
    uploader_id: UUID = Field(..., description="Uploader UserProfile UUID")
    file_name: str = Field(..., description="Resource file name")
    file_url: str = Field(..., description="Object store URL")
    subject_code: str = Field(..., description="Subject code tag")
    created_at: datetime = Field(..., description="Timestamp of upload")
    updated_at: datetime | None = Field(default=None, description="Timestamp of last update")
    uploader_name: str | None = Field(
        default=None,
        description="Full name of the uploader student/faculty",
    )


# Backward-compatibility alias
ResourceRead = ResourceResponse


class ResourcePagination(BaseModel):
    """Paginated list of academic resources."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ResourceResponse] = Field(..., description="List of resources")
    total: int = Field(..., description="Total resources matching query")
    limit: int = Field(default=50, description="Items per page limit")
    offset: int = Field(default=0, description="Page offset")


# Backward-compatibility alias
ResourceList = ResourcePagination


# ── Storage & Direct Upload Schemas ──────────────────────


class SignedUploadUrlRequest(BaseModel):
    """Request payload to generate a pre-signed upload URL for Supabase Storage."""

    file_name: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Name of the file about to be uploaded",
        examples=["Microprocessor_Lab_Manual.pdf"],
    )


class SignedUploadUrlResponse(BaseModel):
    """Pre-signed upload destination metadata for client-side direct upload."""

    model_config = ConfigDict()

    upload_url: str = Field(..., description="Direct storage upload URL")
    file_path: str = Field(..., description="Scoped object storage bucket key")
