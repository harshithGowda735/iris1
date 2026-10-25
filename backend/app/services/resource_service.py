"""
Resource service — Academic REPO channel file indexing and storage URL generation.

Handles uploading notes, syllabus documents, and lab records tagged by subject code.
Provides scoped storage path generation for direct client uploads to Supabase Storage.
"""

from __future__ import annotations

import re
import time
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.membership import NodeMembership
from app.models.profile import UserProfile
from app.models.resource import Resource
from app.schemas.resource import ResourceCreate
from app.services import node_service


class ResourceService:
    """Service layer for academic file repository and storage integration."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _verify_membership(self, user_id: UUID, node_id: UUID) -> None:
        """Verify that user belongs to the target node or one of its ancestors."""
        # Ensure node exists
        await node_service.get_node(self.db, node_id)

        breadcrumbs = await node_service.get_ancestor_path(self.db, node_id)
        ancestor_ids = [b.id for b in breadcrumbs]

        query = select(NodeMembership).where(
            NodeMembership.user_id == user_id,
            NodeMembership.node_id.in_(ancestor_ids),
        )
        membership = (await self.db.execute(query)).scalars().first()
        if membership is None:
            raise ForbiddenError("You are not a member of this node.")

    async def create_resource(
        self, node_id: UUID, user_id: UUID, data: ResourceCreate
    ) -> Resource:
        """Index an uploaded academic file in the node's REPO catalog."""
        await self._verify_membership(user_id, node_id)

        resource = Resource(
            node_id=node_id,
            uploader_id=user_id,
            file_name=data.file_name.strip(),
            file_url=data.file_url.strip(),
            subject_code=data.subject_code.strip().upper(),
        )
        self.db.add(resource)
        await self.db.flush()
        await self.db.refresh(resource)
        await self.db.refresh(resource, attribute_names=["uploader"])
        return resource

    async def get_node_resources(
        self,
        node_id: UUID,
        subject_code: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Resource], int]:
        """Fetch all resources registered for a node, optionally filtered by subject code."""
        # Ensure node exists
        await node_service.get_node(self.db, node_id)

        base_query = (
            select(Resource)
            .where(Resource.node_id == node_id)
            .options(selectinload(Resource.uploader))
        )
        count_query = (
            select(func.count())
            .select_from(Resource)
            .where(Resource.node_id == node_id)
        )

        if subject_code is not None and subject_code.strip():
            normalized = subject_code.strip().upper()
            base_query = base_query.where(Resource.subject_code == normalized)
            count_query = count_query.where(Resource.subject_code == normalized)

        total = (await self.db.execute(count_query)).scalar_one()
        results = await self.db.execute(
            base_query.order_by(Resource.created_at.desc()).limit(limit).offset(offset)
        )
        return list(results.scalars().all()), total

    async def get_resource(self, resource_id: UUID) -> Resource:
        """Fetch a single resource by UUID or raise NotFoundError."""
        query = (
            select(Resource)
            .where(Resource.id == resource_id)
            .options(selectinload(Resource.uploader))
        )
        resource = (await self.db.execute(query)).scalar_one_or_none()
        if resource is None:
            raise NotFoundError("Resource", resource_id)
        return resource

    async def delete_resource(
        self, resource_id: UUID, requesting_user: UserProfile
    ) -> None:
        """Delete an uploaded resource. Only the original uploader may delete."""
        resource = await self.get_resource(resource_id)
        if resource.uploader_id != requesting_user.id:
            raise ForbiddenError("You can only delete resources you uploaded.")
        await self.db.delete(resource)
        await self.db.flush()

    def generate_upload_url(self, file_name: str, node_id: UUID) -> tuple[str, str]:
        """Construct scoped storage path and direct upload URL for Supabase Storage.

        Returns (upload_url, file_path).
        """
        # Sanitize file name
        clean_name = re.sub(r"[^\w\.-]", "_", file_name)
        timestamp = int(time.time())
        bucket = "campus-docs"
        file_path = f"{bucket}/{node_id}/{timestamp}_{clean_name}"

        base_url = settings.supabase_url.rstrip("/")
        upload_url = f"{base_url}/storage/v1/object/{file_path}"
        return upload_url, file_path


# ── Module-Level Delegates (Backwards-Compatibility) ──────


async def create_resource(
    db: AsyncSession,
    payload: ResourceCreate,
    uploader: UserProfile,
) -> Resource:
    target_node = payload.node_id
    if target_node is None:
        raise ValueError("node_id must be provided in payload or route.")
    return await ResourceService(db).create_resource(target_node, uploader.id, payload)


async def list_resources(
    db: AsyncSession,
    node_id: UUID,
    subject_code: str | None = None,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Resource], int]:
    return await ResourceService(db).get_node_resources(
        node_id, subject_code=subject_code, limit=limit, offset=offset
    )


async def get_resource(db: AsyncSession, resource_id: UUID) -> Resource:
    return await ResourceService(db).get_resource(resource_id)


async def delete_resource(
    db: AsyncSession,
    resource_id: UUID,
    requesting_user: UserProfile,
) -> None:
    await ResourceService(db).delete_resource(resource_id, requesting_user)
