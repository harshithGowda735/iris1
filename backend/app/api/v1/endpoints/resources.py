"""
Resource (Academic REPO) endpoints — subject-tagged files and storage upload URL generation.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user, require_node_role
from app.models.profile import UserProfile
from app.models.resource import Resource
from app.schemas.profile import RoleType
from app.schemas.resource import (
    ResourceCreate,
    ResourcePagination,
    ResourceResponse,
    SignedUploadUrlRequest,
    SignedUploadUrlResponse,
)
from app.services.resource_service import ResourceService

# ── Primary Node-Scoped Router (/nodes/{node_id}/resources) ──
router = APIRouter()


def _to_resource_response(r: Resource) -> ResourceResponse:
    """Helper to convert Resource model to ResourceResponse with uploader_name."""
    resp = ResourceResponse.model_validate(r)
    if r.uploader:
        resp.uploader_name = r.uploader.full_name
    return resp


@router.get(
    "",
    response_model=list[ResourceResponse],
    summary="Get all resources for a node (notes, syllabus, lab manuals)",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_node_role(RoleType.MEMBER))],
)
async def get_node_resources(
    node_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    subject_code: Annotated[
        str | None,
        Query(max_length=20, description="Filter materials by subject code (e.g. 21CS32)"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ResourceResponse]:
    """Retrieve all academic resources for a node, optionally filtered by subject code."""
    service = ResourceService(db)
    items, _ = await service.get_node_resources(
        node_id, subject_code=subject_code, limit=limit, offset=offset
    )
    return [_to_resource_response(r) for r in items]


@router.post(
    "",
    response_model=ResourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Index an uploaded academic resource in the REPO",
)
async def create_node_resource(
    node_id: UUID,
    payload: ResourceCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserProfile, Depends(get_current_user)],
) -> ResourceResponse:
    """Register uploaded file metadata and tag it with a subject code."""
    service = ResourceService(db)
    resource = await service.create_resource(node_id, user.id, payload)
    return _to_resource_response(resource)


@router.post(
    "/upload-url",
    response_model=SignedUploadUrlResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate pre-signed upload URL for direct storage upload",
    dependencies=[Depends(require_node_role(RoleType.MEMBER))],
)
async def get_upload_url(
    node_id: UUID,
    payload: SignedUploadUrlRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SignedUploadUrlResponse:
    """Generate a destination bucket path and pre-signed upload URL for Supabase Storage."""
    service = ResourceService(db)
    upload_url, file_path = service.generate_upload_url(payload.file_name, node_id)
    return SignedUploadUrlResponse(upload_url=upload_url, file_path=file_path)


# ── Global & Legacy Collection Router (/resources) ─────────
legacy_router = APIRouter()


@legacy_router.post(
    "",
    response_model=ResourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register an uploaded resource (legacy endpoint)",
)
async def legacy_create_resource(
    payload: ResourceCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserProfile, Depends(get_current_user)],
) -> ResourceResponse:
    target_node = payload.node_id
    if target_node is None:
        raise ValueError("node_id must be provided in request body for this endpoint.")
    service = ResourceService(db)
    resource = await service.create_resource(target_node, user.id, payload)
    return _to_resource_response(resource)


@legacy_router.get(
    "",
    response_model=ResourcePagination,
    summary="List resources (legacy endpoint)",
)
async def legacy_list_resources(
    node_id: Annotated[UUID, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    subject_code: Annotated[str | None, Query(max_length=20)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ResourcePagination:
    service = ResourceService(db)
    items, total = await service.get_node_resources(
        node_id, subject_code=subject_code, limit=limit, offset=offset
    )
    return ResourcePagination(
        items=[_to_resource_response(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@legacy_router.get(
    "/{resource_id}",
    response_model=ResourceResponse,
    summary="Get single resource by UUID",
    status_code=status.HTTP_200_OK,
)
async def get_single_resource(
    resource_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ResourceResponse:
    service = ResourceService(db)
    resource = await service.get_resource(resource_id)
    return _to_resource_response(resource)


@legacy_router.delete(
    "/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
    summary="Delete a resource",
)
async def delete_resource(
    resource_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserProfile, Depends(get_current_user)],
) -> None:
    service = ResourceService(db)
    await service.delete_resource(resource_id, user)
